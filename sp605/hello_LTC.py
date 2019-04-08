"""
Trying to communicate with the LTC2175 chip on a
FMC board trough SPI over UartWishbone Bridge
... wish me luck :p

okay, this works, next step: connect to the LVDS FRAME(_P/N)
signal and measure its frequency, which is sample rate / 2 due to DDR:
f_frame = f_enc / 2

try:
 python3 hello_LTC.py <build / synth / config>
"""
from migen import *
from migen.genlib.io import DifferentialInput, DifferentialOutput
from migen.genlib.cdc import MultiReg
from litex.boards.platforms import sp605
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.interconnect.wishbone import SRAM
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart, spi, frequency_meter
from sp605_crg import SP605_CRG
from sys import argv, exit, path
from shutil import copyfile
from dsp.Acquisition import Acquisition
path.append("iserdes")
from ltc_phy import LTCPhy


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCCore, AutoCSR):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "lvds",
        "acq"
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
            ident="LTC2175 demonstrator", ident_version=True
        )
        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        self.add_cpu(uart.UARTWishboneBridge(
            platform.request("serial"),
            sys_clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # Clock Reset Generation
        self.submodules.crg = SP605_CRG(platform, sys_clk_freq)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  FMC LPC connectivity
        # ----------------------------
        platform.add_extension(LTCPhy.pads)

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = platform.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)

        # ----------------------------
        #  LVDS phy
        # ----------------------------
        self.submodules.lvds = LTCPhy(platform, 800e6 / 7)

        # ----------------------------
        #  Shared memory for ADC data
        # ----------------------------
        mem = Memory(16, 4096)
        self.specials += mem
        self.submodules.sample_ram = SRAM(mem, read_only=True)
        self.register_mem("sample", 0x50000000, self.sample_ram.bus, 4096)
        self.submodules.acq = Acquisition(mem)
        self.specials += MultiReg(
            self.platform.request("user_btn"), self.acq.trigger
        )
        self.comb += [
            self.platform.request("user_led").eq(self.acq.busy),
            self.acq.data_in.eq(self.lvds.sample_out),
            self.acq.sample.clk.eq(self.lvds.sample.clk)
        ]

        # ----------------------------
        #  Provide a 114 MHz ENC clock signal on SMA_GPIO
        # ----------------------------
        enc_out = Signal()
        self.specials += Instance(
            "ODDR2",
            o_Q=enc_out,
            i_C0=ClockSignal("clk_114"),
            i_C1=~ClockSignal("clk_114"),
            i_CE=1,
            i_D0=1,
            i_D1=0
        )
        gpio_pads = platform.request("ENC_CLK")
        self.specials += DifferentialOutput(enc_out, gpio_pads.p, gpio_pads.n)




if __name__ == '__main__':
    if len(argv) < 2:
        print(__doc__)
        exit(-1)
    tName = argv[0].replace(".py", "")
    p = sp605.Platform()
    soc = HelloLtc(p)
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv=None,
            compile_gateware=False, compile_software=False
        )
        builder.build(build_name=tName)
        # Ugly workaround as I couldn't get vpath to work :(
        tName += ".v"
        copyfile("./build/gateware/" + tName, tName)
        copyfile("./build/gateware/mem.init", "mem.init")
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=True, compile_software=True
        )
        builder.build(build_name=tName)
        # Ugly workaround as I couldn't get vpath to work :(
        copyfile("./build/gateware/" + tName + "_synth.v", tName + ".v")
    if "config" in argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
