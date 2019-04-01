"""
Trying to communicate with the LTC2175 chip on a
FMC board trough SPI over UartWishbone Bridge
... wish me luck :p

okay, this works, next step: connect to the LVDS FRAME(_P/N)
signal and measure its frequency, which is sample rate / 2 due to DDR:
f_frame = f_enc / 2

python3 hello_LTC.py <build / config>
"""
from migen import *
from migen.genlib.io import DifferentialInput, DifferentialOutput
from litex.boards.platforms import sp605
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart, spi, frequency_meter
from sp605_crg import SP605_CRG
from sp6iserdes_lt.IserdesSp6 import LTCPhy
from sys import argv, exit


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCCore):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "f_frame",
        "lvds"
    ]
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    def __init__(self, platform, **kwargs):
        sys_clk_freq = int(100e6) # 100 MHz, 10 ns
        SoCCore.__init__(
            self, platform, sys_clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="Wir trampeln durchs Getreide ...", ident_version=True
        )
        #----------------------------
        # Serial to Wishbone bridge
        #----------------------------
        self.add_cpu(uart.UARTWishboneBridge(
            platform.request("serial"),
            sys_clk_freq,
            baudrate=115200
        ))
        self.add_wb_master(self.cpu.wishbone)

        # Clock Reset Generation
        self.submodules.crg = SP605_CRG(platform, sys_clk_freq)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # Blinky
        led = platform.request("user_led")
        counter = Signal(26)
        self.comb += led.eq(counter[-1])
        self.sync += counter.eq(counter + 1)

        # FMC LPC connectivity
        ltc_connection = [
            ("LTC_SPI", 0,
                Subsignal("cs_n", Pins("LPC:LA14_P")),
                Subsignal("miso", Pins("LPC:LA14_N"), Misc("PULLUP")),
                Subsignal("mosi", Pins("LPC:LA27_P")),
                Subsignal("clk",  Pins("LPC:LA27_N")),
                IOStandard("LVCMOS25")
            ),
            ("LTC_OUT", 0,  # Bank 0
                Subsignal("a_p", Pins("LPC:LA03_P")),
                Subsignal("a_n", Pins("LPC:LA03_N")),
                Subsignal("b_p", Pins("LPC:LA08_P")),
                Subsignal("b_n", Pins("LPC:LA08_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            ("LTC_OUT", 1,  # Bank 0
                Subsignal("a_p", Pins("LPC:LA12_P")),
                Subsignal("a_n", Pins("LPC:LA12_N")),
                Subsignal("b_p", Pins("LPC:LA16_P")),
                Subsignal("b_n", Pins("LPC:LA16_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            ("LTC_OUT", 2,  # Bank 2
                Subsignal("a_p", Pins("LPC:LA22_P")),
                Subsignal("a_n", Pins("LPC:LA22_N")),
                Subsignal("b_p", Pins("LPC:LA25_P")),
                Subsignal("b_n", Pins("LPC:LA25_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            ("LTC_OUT", 3,  # Bank 2
                Subsignal("a_p", Pins("LPC:LA29_P")),
                Subsignal("a_n", Pins("LPC:LA29_N")),
                Subsignal("b_p", Pins("LPC:LA31_P")),
                Subsignal("b_n", Pins("LPC:LA31_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            ("LTC_FR", 0,  # Bank 2
                Subsignal("p", Pins("LPC:LA18_CC_P")),
                Subsignal("n", Pins("LPC:LA18_CC_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            ("LTC_DCO", 0,  # Bank 2
                Subsignal("p", Pins("LPC:LA17_CC_P")),
                Subsignal("n", Pins("LPC:LA17_CC_N")),
                IOStandard("LVDS_25"),
                Misc("DIFF_TERM=TRUE")
            ),
            # Connect GPIO_SMA on SP605 with CLK input on 1525A
            # Alternatively, use a Si570 eval board as clock source
            ("ENC_CLK", 0,
                Subsignal("p", Pins("SMA_GPIO:P")),
                Subsignal("n", Pins("SMA_GPIO:N")),
                # Note: the LTC eval board needs to be modded
                # to accept a differential clock
                IOStandard("LVDS_25")
            )
        ]
        platform.add_extension(ltc_connection)

        # SPI master
        spi_pads = platform.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)
        self.comb += platform.request("user_led").eq(~spi_pads.cs_n)

        # Measure frame rate
        # Accumulates `frm` cycles for 100e6 cycles of 1 ns each = [Hz]
        self.submodules.f_frame = frequency_meter.FrequencyMeter(int(100e6))
        frm_pads = platform.request("LTC_FR")
        frm_se = Signal()
        self.specials += DifferentialInput(frm_pads.p, frm_pads.n, frm_se)
        self.comb += self.f_frame.clk.eq(frm_se)
        self.comb += platform.request("user_led").eq(frm_se)

        # LVDS phy
        self.submodules.lvds = LTCPhy(platform)

        # Provide a 114 MHz ENC clock signal on SMA_GPIO
        enc_out = Signal()
        self.specials += Instance(
            "ODDR2",
            o_Q=enc_out,
            i_C0=self.crg.clk_114,
            i_C1=~self.crg.clk_114,
            i_CE=1,
            i_D0=1,
            i_D1=0
        )
        gpio_pads = platform.request("ENC_CLK")
        self.specials += DifferentialOutput(
            enc_out,
            gpio_pads.p,
            gpio_pads.n
        )


if __name__ == '__main__':
    p = sp605.Platform()
    soc = HelloLtc(p)
    if len(argv) < 2:
        print(__doc__)
        exit(-1)
    if "build" in argv:
        builder = Builder(soc, output_dir="build", csr_csv="build/csr.csv")
        builder.build()
    if "config" in argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/gateware/top.bit")
