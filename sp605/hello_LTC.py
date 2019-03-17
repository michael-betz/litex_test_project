"""
Trying to communicate with the LTC2175 chip on a
FMC board trough SPI over UartWishbone Bridge
... wish me luck :p

python3 hello_LTC.py <build / config>
"""
from migen import *
from litex.boards.platforms import sp605
from litex.build.generic_platform import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart, spi
from sp605_crg import SP605_CRG
from sys import argv, exit


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCCore):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi"
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

        # SPI master
        spi_ext = [("LTC_SPI", 0,
            Subsignal("cs_n", Pins("LPC:LA14_P")),
            Subsignal("miso", Pins("LPC:LA14_N"), Misc("PULLUP")),
            Subsignal("mosi", Pins("LPC:LA27_P")),
            Subsignal("clk",  Pins("LPC:LA27_N")),
            IOStandard("LVCMOS18")
        )]
        platform.add_extension(spi_ext)
        spi_pads = platform.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)
        self.comb += platform.request("user_led").eq(spi_pads.cs_n == 0)


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
