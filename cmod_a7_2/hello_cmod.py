"""
Hello world example for the CMODA7
In FPGA world that is blinkng a LED
"""
import sys
from migen import *
from cmod_a7 import *
from base import _CRG

class HelloCmod(_CRG):
    def __init__(self, platform):
        _CRG.__init__(self, platform, sys_clk_freq=int(100e6))
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
