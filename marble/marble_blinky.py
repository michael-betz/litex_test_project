"""
Hello world (blinking LED) example for the Marble board with litex
"""
import sys
from migen import *
from marble import Platform

p = Platform()


def main():
    led = p.request("user_led")
    module = Module()
    # 20 MHz / 2**24 = 1.19 Hz
    counter = Signal(24)
    module.comb += led.eq(counter[-1])
    module.sync += counter.eq(counter + 1)
    p.build(module)


if __name__ == '__main__':
    if "load" in sys.argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        main()
