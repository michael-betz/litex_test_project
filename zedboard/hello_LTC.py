"""
Trying to communicate with the LTC2175 chip on a
FMC board trough SPI over UartWishbone Bridge
... wish me luck :p

python3 hello_LTC.py <build / config>
"""
from migen import *
from litex.boards.platforms import zedboard
from litex.build.generic_platform import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, xadc, uart, clock
from sys import argv, exit


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCCore):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna"
    ]
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    def __init__(self, platform, **kwargs):
        sys_clk_freq = int(1e9 / platform.default_clk_period) # 100 MHz, 10 ns
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
        self.submodules.crg = CRG(platform.request("clk100"), platform.request("user_btn"))

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # Blinky
        led = platform.request("user_led")
        counter = Signal(24)
        self.comb += led.eq(counter[-1])
        self.sync += counter.eq(counter + 1)


if __name__ == '__main__':
    platform = zedboard.Platform()
    soc = HelloLtc(platform)
    if len(argv) != 2:
        print(__doc__)
        exit(-1)
    if argv[1] == "build":
        builder = Builder(soc, output_dir="build", csr_csv="csr.csv")
        builder.build()
    elif argv[1] == "config":
        prog = platform.create_programmer()
        prog.load_bitstream("build/gateware/top.bit")
    else:
        print(__doc__)
        exit(-1)
