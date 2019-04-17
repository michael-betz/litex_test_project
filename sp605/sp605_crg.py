from migen import *
from migen.genlib.io import DifferentialInput
from migen.genlib.resetsync import AsyncResetSynchronizer
from fractions import Fraction


class SP605_CRG(Module):
    """
    Clock and reset generator for SP605 (driven by the 200 MHz on-board crystal)
    """
    def __init__(self, platform, clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.clk_114 = ClockDomain()

        f0 = 1e9 / platform.default_clk_period

        p_clk = platform.request(platform.default_clk_name)
        se_clk = Signal()

        self.specials += Instance(
            "IBUFGDS",
            i_I=p_clk.p,
            i_IB=p_clk.n,
            o_O=se_clk
        )

        f = Fraction(int(clk_freq), int(f0))
        n, m, p = f.denominator, f.numerator, 8
        assert f0 / n * m == clk_freq
        pll_lckd = Signal()
        pll_fb = Signal()
        pll = Signal(6)
        rst = platform.request("cpu_reset")
        mult = 6  # vco at 1.2 GHz
        self.specials.pll = Instance("PLL_ADV",
                                     name="PLL_CRG",
                                     p_SIM_DEVICE="SPARTAN6",
                                     p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                                     p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                                     i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0, i_RST=rst, i_REL=0,
                                     p_DIVCLK_DIVIDE=1, p_CLKFBOUT_MULT=mult, p_CLKFBOUT_PHASE=0.,
                                     i_CLKIN1=se_clk, i_CLKIN2=0, i_CLKINSEL=1,
                                     p_CLKIN1_PERIOD=1000000000/f0, p_CLKIN2_PERIOD=0.,
                                     i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_lckd,
                                     o_CLKOUT0=pll[0], p_CLKOUT0_DUTY_CYCLE=.5,
                                     o_CLKOUT1=pll[1], p_CLKOUT1_DUTY_CYCLE=.5,
                                     o_CLKOUT2=pll[2], p_CLKOUT2_DUTY_CYCLE=.5,
                                     o_CLKOUT3=pll[3], p_CLKOUT3_DUTY_CYCLE=.5,
                                     o_CLKOUT4=pll[4], p_CLKOUT4_DUTY_CYCLE=.5,
                                     o_CLKOUT5=pll[5], p_CLKOUT5_DUTY_CYCLE=.5,
                                     p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=31,
                                     p_CLKOUT1_PHASE=0., p_CLKOUT1_DIVIDE=31,
                                     p_CLKOUT2_PHASE=0., p_CLKOUT2_DIVIDE=31,
                                     p_CLKOUT3_PHASE=0., p_CLKOUT3_DIVIDE=31,
                                     p_CLKOUT4_PHASE=0., p_CLKOUT4_DIVIDE=8,  # sys = 150 MHz
                                     p_CLKOUT5_PHASE=0., p_CLKOUT5_DIVIDE=10  # adc = 120 MHz
        )
        print("sys", 200 * mult / 8)
        print("clk_114", 200 * mult / 10)
        self.specials += Instance("BUFG", i_I=pll[4], o_O=ClockSignal("sys"))
        self.specials += Instance("BUFG", i_I=pll[5], o_O=ClockSignal("clk_114"))
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll_lckd)
        self.specials += AsyncResetSynchronizer(self.clk_114, ~pll_lckd)
