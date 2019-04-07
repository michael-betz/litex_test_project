"""\
Spartan6 ISERDES receiver for LVDS ADCs

Clock and data lanes must be in phase (edge aligned)
The clock lane does not need to transition with every bit,
as it will be multiplied up by factor M with a PLL_ADV.

The bits of the clock lane are also recovered, which can
be helpfule with frame alignment.

This is basically a migen mash up of
 * serdes_1_to_n_clk_pll_s8_diff.v
 * serdes_1_to_n_data_s8_diff.v
 * litevideo/datacapture.py

Migen can't handle the simulation of Xilinx hardware primitives
like PLL or IDELAY
hence this python file is only used to generate verilog code,
which is then simulated traditionally in iverilog.

try `python3 IserdesSp6_pll.py build`
or `make view`
"""

from sys import path, argv
from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from migen.genlib.cdc import AsyncResetSynchronizer
from IserdesSp6_common import IserdesSp6_common, genVerilog
path.append("..")
from general import *


class IserdesSp6_pll(IserdesSp6_common):
    def __init__(
        self, S=8, D=2, M=2, MIRROR_BITS=False, DCO_PERIOD=2.0, **kwargs
    ):
        """
        Clock and data lanes must be in-phase (edge aligned)

        S = serialization factor (bits per frame)
        D = number of parallel lanes

        M = clock multiplier (bits per DCO period)
            1 for sdr, 2 for ddr, higher for a divided clock

        DCO_PERIOD = period of dco_p/n in [ns] for PLL_ADV

        MIRROR_BITS = False:
            first bit of the serial stream clocked in ends up in the
            LSB of data_outs

        See IserdesSp6_common.py for input output ports
        """

        # Data recovered from the clock lane for frame alignment (in case of a divided clock)
        self.clk_data_out = Signal(8)

        # High when sample clock is stable
        self.pll_locked = Signal()

        ###

        # Add data lanes and control signals
        IserdesSp6_common.__init__(
            self, S, D, MIRROR_BITS,
            {"p_DATA_RATE": "SDR"},
            {"p_DATA_RATE": "SDR"}
        )

        # Sync resets
        self.specials += AsyncResetSynchronizer(self.sample, ~self.pll_locked)

        # -------------------------------------
        #  Iserdes PLL clocking scheme
        # -------------------------------------
        # ... with clk-data recovery
        self.dco = Signal()
        self.specials += DifferentialInput(self.dco_p, self.dco_n, self.dco)
        dco_m = Signal()
        dco_s = Signal()
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="MASTER",
            p_IDELAY_TYPE="VARIABLE_FROM_HALF_MAX",
            i_IDATAIN=self.dco,
            i_CAL=self.idelay_cal_m,
            i_CE=0,
            i_INC=0,
            o_DATAOUT=dco_m,
            **self.idelay_default
        )
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="SLAVE",
            p_IDELAY_TYPE="FIXED",
            i_IDATAIN=self.dco,
            i_CAL=0,
            i_CE=0,
            i_INC=0,
            o_DATAOUT=dco_s,
            **self.idelay_default
        )
        cascade_up = Signal()
        cascade_down = Signal()
        dfb = Signal()
        cfb0 = Signal()
        self.specials += Instance(
            "ISERDES2",
            p_SERDES_MODE="MASTER",
            i_D=dco_m,
            i_SHIFTIN=cascade_up,
            o_Q4=self.clk_data_out[7],
            o_Q3=self.clk_data_out[6],
            o_Q2=self.clk_data_out[5],
            o_Q1=self.clk_data_out[4],
            o_SHIFTOUT=cascade_down,
            **self.iserdes_default
        )
        # Using the delay matched BUFIO2 and BUFIO2FB,
        # the PLL will generate a ioclock which is phase-
        # aligned with the dco clock at the input of the
        # ISERDES
        self.specials += Instance(
            "ISERDES2",
            p_SERDES_MODE="SLAVE",
            i_D=dco_s,
            i_SHIFTIN=cascade_down,
            o_Q4=self.clk_data_out[3],
            o_Q3=self.clk_data_out[2],
            o_Q2=self.clk_data_out[1],
            o_Q1=self.clk_data_out[0],
            o_SHIFTOUT=cascade_up,
            o_DFB=dfb,
            o_CFB0=cfb0,
            **self.iserdes_default
        )
        pll_clkin = Signal()
        pll_clkfbin = Signal()
        self.specials += Instance(
            "BUFIO2",
            p_DIVIDE_BYPASS="TRUE",
            i_I=dfb,
            o_DIVCLK=pll_clkin
        )
        self.specials += Instance(
            "BUFIO2FB",
            p_DIVIDE_BYPASS="TRUE",
            i_I=cfb0,
            o_O=pll_clkfbin
        )
        pll_clk0 = Signal()
        pll_clk2 = Signal()
        self.specials += Instance(
            "PLL_ADV",
            name="PLL_IOCLOCK",
            p_BANDWIDTH="OPTIMIZED",
            p_SIM_DEVICE="SPARTAN6",
            p_CLKIN1_PERIOD=DCO_PERIOD,
            p_CLKIN2_PERIOD=DCO_PERIOD,
            p_DIVCLK_DIVIDE=1,
            p_CLKFBOUT_MULT=M,
            p_CLKFBOUT_PHASE=0.0,
            p_CLKOUT0_DIVIDE=1,
            p_CLKOUT2_DIVIDE=S,
            p_CLKOUT0_DUTY_CYCLE=0.5,
            p_CLKOUT2_DUTY_CYCLE=0.5,
            p_CLKOUT0_PHASE=0.0,
            p_CLKOUT2_PHASE=0.0,
            p_COMPENSATION="SOURCE_SYNCHRONOUS",
            # p_COMPENSATION="INTERNAL",
            p_CLK_FEEDBACK="CLKOUT0",

            i_RST=self.reset,
            i_CLKINSEL=1,
            i_CLKIN1=pll_clkin,
            i_CLKIN2=0,
            i_CLKFBIN=pll_clkfbin,
            # o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,

            i_DADDR=Signal(5),
            i_DI=Signal(16),
            i_DEN=0,
            i_DWE=0,
            i_DCLK=0,

            o_CLKOUT0=pll_clk0,
            o_CLKOUT2=pll_clk2,
            o_LOCKED=self.pll_locked
        )
        self.specials += Instance(
            "BUFPLL",
            p_DIVIDE=S,
            i_PLLIN=pll_clk0,
            i_GCLK=ClockSignal("sample"),
            i_LOCKED=self.pll_locked,
            o_IOCLK=self.ioclk_p,
            o_SERDESSTROBE=self.serdesstrobe
        )
        self.specials += Instance(
            "BUFG",
            i_I=pll_clk2,
            o_O=ClockSignal("sample")
        )
        # ioclk_n is not needed, hardwire it to zero
        self.comb += self.ioclk_n.eq(0)

    def getIOs(self):
        """ add this classes additional IOs to the set """
        return IserdesSp6_common.getIOs(self) | {
            self.clk_data_out, self.pll_locked
        }


if __name__ == "__main__":
    if "build" not in argv:
        print(__doc__)
        exit(-1)
    genVerilog(IserdesSp6_pll)
