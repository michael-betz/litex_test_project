"""\
 7-series ISERDES receiver for LVDS ADCs

 DCO is a DDR clock signal, doing one transition for every bit.
 This transition happens when data is stable (90 deg phase shift)

 try `python3 s7_iserdes.py build`
 """

from sys import argv
from migen import *
from migen.build.xilinx.common import xilinx_special_overrides
from migen.genlib.cdc import AsyncResetSynchronizer
from migen.genlib.io import DifferentialInput
from migen.genlib.misc import timeline


class S7_iserdes(Module):
    def __init__(self, S=8, D=2, INITIAL_IDELAY=15, clock_regions=[0, 1]):
        """
        S = serialization factor (bits per frame)
        D = number of parallel lanes
        clock_regions:
            must be list of D integers
            indicates which clock region the input signal belongs to
            each clock_region will have its own BUFR and BUFIOs, driving the ISERDES's
            example for 3 signals, where the last one is in a separate clock region:
            clock_regions = [0, 0, 1]
        """

        # LVDS DDR bit clock
        self.dco_p = Signal()
        self.dco_n = Signal()

        # data (+frame) lanes
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)

        self.bitslip = Signal()  # Pulse to rotate (sample clock domain)

        # IDELAY control for DCO clock input
        # on sys clock domain
        self.id_inc = Signal()
        self.id_dec = Signal()
        self.id_value = Signal(5)

        # parallel data out, S-bit serdes on D-lanes
        # on `sample` clock domain
        self.data_outs = [Signal(S) for i in range(D)]

        ###
        self.initial_tl_done = Signal()

        self.clock_domains.cd_sample = ClockDomain("sample", reset_less=True)   # recovered ADC sample clock

        self.iserdes_default = {
            "p_DATA_WIDTH": S,
            "p_DATA_RATE": "DDR",
            "p_SERDES_MODE": "MASTER",
            "p_INTERFACE_TYPE": "NETWORKING",
            "p_NUM_CE": 1,
            "p_IOBDELAY": "NONE",

            "i_DDLY": 0,
            "i_CE1": 1,
            "i_CE2": 1,
            "i_DYNCLKDIVSEL": 0,
            "i_DYNCLKSEL": 0,
            "i_RST": ~self.initial_tl_done,
            "i_BITSLIP": self.bitslip
        }

        # -------------------------------------------------
        #  DCO input clock --> IDELAYE2 --> BUFMRCE
        # -------------------------------------------------
        self.clock_domains.cd_dco = ClockDomain("dco", reset_less=True)
        dco_delay = Signal()
        dco_delay_2 = Signal()
        id_CE = Signal()
        self.comb += id_CE.eq(self.id_inc ^ self.id_dec)
        self.specials += DifferentialInput(self.dco_p, self.dco_n, ClockSignal("dco"))
        self.specials += Instance("IDELAYE2",
            p_DELAY_SRC="IDATAIN",
            p_HIGH_PERFORMANCE_MODE="TRUE",
            p_REFCLK_FREQUENCY=200.0,
            p_IDELAY_TYPE="VARIABLE",
            p_IDELAY_VALUE=INITIAL_IDELAY,

            i_C=ClockSignal("sys"),
            i_LD=ResetSignal("sys"),
            i_INC=self.id_inc,
            i_CE=id_CE,
            i_LDPIPEEN=0,
            i_CINVCTRL=0,
            i_CNTVALUEIN=Constant(0, 5),
            i_DATAIN=0,
            i_REGRST=0,
            i_IDATAIN=ClockSignal("dco"),

            o_DATAOUT=dco_delay,
            o_CNTVALUEOUT=self.id_value
        )

        bufmr_ce = Signal()
        bufr_clr = Signal(reset=1)
        self.specials += Instance("BUFMRCE",
            i_CE=bufmr_ce,
            i_I=dco_delay,
            o_O=dco_delay_2
        )

        # synchronize BUFR dividers on sys_clk reset
        # a symptom of screwing this up is:
        #   different number of bitslips are required
        #   for ISERDES on different clock domains
        self.sync += timeline(
            ~self.initial_tl_done,
            [
                (0, [bufr_clr.eq(1), bufmr_ce.eq(0)]),
                (1, [bufmr_ce.eq(1)]),
                (2, [bufr_clr.eq(0)]),
                (5, [self.initial_tl_done.eq(1)])
            ]
        )

        # -------------------------------------------------
        #  generate a BUFR and BUFIO for each clock region
        # -------------------------------------------------
        io_clks = []
        sample_clks = []
        for i in range(max(clock_regions) + 1):
            io_clk = Signal()
            sample_clk = Signal()
            self.specials += Instance("BUFIO",
                i_I=dco_delay_2,
                o_O=io_clk
            )
            self.specials += Instance("BUFR",
                p_BUFR_DIVIDE=str(S),
                i_I=dco_delay_2,
                i_CE=1,
                i_CLR=bufr_clr,
                o_O=sample_clk
            )
            io_clks.append(io_clk)
            sample_clks.append(sample_clk)

        # Make `sample` clock globally available
        # self.specials += Instance(
        #     "BUFG",
        #     i_I=sample_clk,
        #     o_O=ClockSignal("sample")
        # )
        self.comb += ClockSignal("sample").eq(sample_clk)

        # -------------------------------------------------
        #  Generate an IDERDES for each data lane
        # -------------------------------------------------
        for d_p, d_n, d_o, c_reg in zip(
            self.lvds_data_p,
            self.lvds_data_n,
            self.data_outs,
            clock_regions
        ):
            d_i = Signal()
            self.specials += DifferentialInput(d_p, d_n, d_i)
            self.specials += Instance("ISERDESE2",
                **self.iserdes_default,
                i_CLK=io_clks[c_reg],
                i_CLKB=~io_clks[c_reg],
                i_CLKDIV=sample_clks[c_reg],
                i_D=d_i,
                o_Q1=d_o[0],
                o_Q2=d_o[1],
                o_Q3=d_o[2],
                o_Q4=d_o[3],
                o_Q5=d_o[4],
                o_Q6=d_o[5],
                o_Q7=d_o[6],
                o_Q8=d_o[7]
            )

    def getIOs(self):
        """ for easier interfacing to testbench """
        return {
            self.dco_p,
            self.dco_n,
            self.lvds_data_p,
            self.lvds_data_n,
            self.bitslip,
            self.id_inc,
            self.id_dec,
            self.id_value,
            *self.data_outs
        }


if __name__ == "__main__":
    """
    for simulating with test/sp6_ddr_tb.v in Icarus
    """
    if "build" not in argv:
        print(__doc__)
        exit(-1)
    from migen.fhdl.verilog import convert
    tName = argv[0].replace(".py", "")
    d = S7_iserdes(S=8, D=1, clock_regions=[0])
    convert(
        d,
        ios=d.getIOs(),
        special_overrides=xilinx_special_overrides,
        # create_clock_domains=False,
        name=tName
    ).write(tName + ".v")

