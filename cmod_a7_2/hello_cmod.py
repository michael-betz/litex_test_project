"""
Hello world example for the CMODA7
In FPGA world that is blinkng a LED
"""
import sys
from migen import *
from cmod_a7 import *

p = Platform()


def main():
    led = p.request("user_led")
    module = Module()
    # 12e6 Hz / 2**(23) = 1.430511474609375 Hz
    counter = Signal(23)
    module.comb += led.eq(counter[-1])
    module.sync += counter.eq(counter + 1)
    p.build(module)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "prog":
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        main()
