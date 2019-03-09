"""
Hello world example for the CMODA7
In FPGA world that is blinkng a LED
"""
import sys
from migen import *
from litex.boards.platforms.cmod_a7 import Platform
from litex.boards.targets.cmod_a7 import _CRG


class HelloCmod(_CRG):
    def __init__(self, platform):
        _CRG.__init__(self, platform, int(100e6))
        led = platform.request("user_led")
        #  12e6 Hz / 2**(23) =  1.430511474609375 Hz
        # 100e6 Hz / 2**(23) = 11.920928955078125 Hz
        counter = Signal(23)
        self.comb += led.eq(counter[-1])
        self.sync += counter.eq(counter + 1)


if __name__ == '__main__':
    p = Platform()
    if len(sys.argv) > 1 and sys.argv[1] == "prog":
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        hc = HelloCmod(p)
        p.build(hc)
