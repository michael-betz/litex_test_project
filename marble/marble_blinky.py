"""
Hello world (blinking LED) example for the Marble board with litex
"""
import sys
from migen import *
from litex_boards.platforms.berkeleylab_marble import Platform

p = Platform()


def main():
    led = p.request("user_led")
    module = Module()
    # 125 MHz / 2**27 = 0.93 Hz
    counter = Signal(27)

    # Blink LED
    module.comb += led.eq(counter[-1])

    # Demo the RTS signal
    # ser_pads = p.request('serial')
    # module.comb += led.eq(ser_pads.rts)

    module.sync += counter.eq(counter + 1)
    p.build(module)


if __name__ == '__main__':
    if "load" in sys.argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        main()
