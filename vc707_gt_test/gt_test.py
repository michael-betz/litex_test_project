"""
AD9174-FMC-EBZ board on VC707

See if we can receive a 128 MHz clock from
HMC7044 through the FMC (on GBTCLK0_M2C)

Demonstrate by blinking a LED
"""
import sys
from migen import *
from migen.genlib.io import CRG
from migen.genlib.resetsync import AsyncResetSynchronizer
from xdc import vc707


class GtTest(Module):
    def __init__(self, p):
        self.submodules += CRG(p.request(p.default_clk_name))
        self.clock_domains.dsp = ClockDomain("dsp")
        self.specials += AsyncResetSynchronizer(self.dsp, ResetSignal('sys'))
        refclk_pads = p.request("sgmii_clock")
        self.specials += Instance(
            "IBUFDS_GTE2",
            i_CEB=0,
            i_I=refclk_pads.p,
            i_IB=refclk_pads.n,
            o_O=ClockSignal('dsp')
        )

        # 156.25 MHz / 2**26 = 2.33 Hz
        counter0 = Signal(26)
        self.sync += counter0.eq(counter0 + 1)
        self.comb += p.request("user_led").eq(counter0[-1])

        # 125.00 MHz / 2**26 = 1.86 Hz
        counter1 = Signal(26)
        self.sync.dsp += counter1.eq(counter1 + 1)
        self.comb += p.request("user_led").eq(counter1[-1])


def main(p):
    gt_test = GtTest(p)
    p.build(gt_test)


if __name__ == '__main__':
    p = vc707.Platform()
    if "config" in sys.argv:
        prog = p.create_programmer()
        prog.load_bitstream("build/top.bit")
    else:
        main(p)
