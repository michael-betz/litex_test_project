#!/home/michael/miniconda3/bin/python
"""
    python base_cpu.py <param>

    build:
        Synthesize / compile:
    build_lib:
        Recompile C support libraries:
    config:
        Load bitfile into fpga
"""
from migen import *
from litex.boards.platforms import cmod_a7
from litex.build.generic_platform import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, xadc, uart
from ios import Led, RGBLed, Button
from sys import argv, exit

# create our soc (fpga description)
class BaseSoC(SoCCore):
    def __init__(self, platform, **kwargs):
        sys_clk_freq = int(1 / platform.default_clk_period * 1000000000)
        SoCCore.__init__(self, platform, sys_clk_freq,
            cpu_type="vexriscv",
            # cpu_variant="debug",
            # cpu_type="picorv32",
            # cpu_type="lm32",
            csr_data_width=32,
            integrated_rom_size=0x8000,
            integrated_main_ram_size=16 * 1024,
            ident="Wir trampeln durchs Getreide ...", ident_version=True
        )

        for c in [
            "dna",
            "xadc",
            "rgbled",
            "leds",
            # "switches",
            "buttons"
            # "adxl362",
            # "display"
        ]:
            self.add_csr(c)

        # self.submodules.bridge = uart.UARTWishboneBridge(platform.request("serial"), sys_clk_freq, baudrate=115200)
        # self.add_wb_master(self.bridge.wishbone)
        # self.register_mem("vexriscv_debug", 0xf00f0000, self.cpu_or_bridge.debug_bus, 0x10)

        # Clock Reset Generation
        self.submodules.crg = CRG(platform.request("clk12"), platform.request("user_btn"))

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # FPGA Temperature/Voltage
        self.submodules.xadc = xadc.XADC()

        # Led
        user_leds = Cat(*[platform.request("user_led") for i in range(2)])
        self.submodules.leds = Led(user_leds)

        # Buttons
        user_buttons = Cat(*[platform.request("user_btn") for i in range(1)])
        self.submodules.buttons = Button(user_buttons)

        # RGB Led
        self.submodules.rgbled = RGBLed(platform.request("rgb_leds"))


if __name__ == '__main__':
    platform = cmod_a7.Platform()
    soc = BaseSoC(platform)
    if len(argv) != 2:
        print(__doc__)
        exit(-1)
    if argv[1] == "build":
        builder = Builder(soc, output_dir="build", csr_csv="csr.csv")
        builder.build()
    elif argv[1] == "build_lib":
        builder = Builder(soc, output_dir="build", compile_gateware=False, compile_software=True, csr_csv="csr.csv")
        builder.build()
    elif argv[1] == "config":
        prog = platform.create_programmer()
        prog.load_bitstream("build/gateware/top.bit")
    else:
        print(__doc__)
        exit(-1)
