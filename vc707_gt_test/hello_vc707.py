"""
Hello world (blinking LED) example for the vc707 with litex
"""
import sys
from migen import *
from xdc import vc707

p = vc707.Platform()


def main():
    led = p.request("user_led")
    module = Module()
    # 100e6 Hz / 2**26 = 1.49 Hz
    counter = Signal(26)
    module.comb += led.eq(counter[25])
    module.sync += counter.eq(counter + 1)
    p.build(module)


if __name__ == '__main__':
    if "config" in sys.argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        main()
