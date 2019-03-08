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
    parser.add_argument(
        "action",
        choices=["build", "synth", "load", "all"],
        help="what to do"
    )
    args = parser.parse_args()
    kwargs = vars(args)
    kwargs["no_compile_firmware"] = False
    kwargs["no_compile_gateware"] = False
    if kwargs["action"] in ("build", "all"):
        kwargs["no_compile_gateware"] = True
    elif kwargs["action"] in ("synth", "all"):
        kwargs["no_compile_firmware"] = True
    soc = MySoc(**kwargs)
    if kwargs["action"] == "load":
        prg = soc.platform.create_programmer()
        prg.load_bitstream("soc_mysoc_cmod_a7/gateware/top.bit")
        return 0
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
