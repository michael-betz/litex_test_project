"""
Example of a customized SOC based on the cmodA7 litex target
"""
from migen import *
from cmod_a7 import *
from base import *

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    builder_args(parser)
    soc_core_args(parser)
    parser.set_defaults(cpu_type="vexriscv", no_compile_gateware=True)
    parser.add_argument("--platform", type=str, default=None,
                        help="Build with the verilator platform for sim")
    args = parser.parse_args()
    print(args)
    soc = BaseSoC(platform=args.platform, **soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
