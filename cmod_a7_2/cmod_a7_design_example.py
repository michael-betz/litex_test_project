"""
Example of a customized SOC based on the cmodA7 litex target
"""
from migen import *
from cmod_a7 import *
from target import *


class Blinky(Module):
    def __init__(self, out):
        counter = Signal(23)
        self.comb += out.eq(counter[-1])
        self.sync += counter.eq(counter + 1)


class MySoc(BaseSoC):
    def __init__(self, **kwargs):
        BaseSoC.__init__(self, **kwargs)
        self.submodules += Blinky(self.platform.request("user_led"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    builder_args(parser)
    BaseSoC.basesoc_args(parser)
    parser.set_defaults(
        integrated_rom_size=0x8000,
        integrated_main_ram_size=0x8000,
        # integrated_sram_size=0,   # Litex will complain if 0!
        cpu_type="picorv32"
    )
    args = parser.parse_args()
    soc = MySoc(**vars(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
