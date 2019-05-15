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


class S7_iserdes(Module):
    def __init__(self, S=8, D=2):
        """
        S = serialization factor (bits per frame)
        D = number of parallel lanes
        """

        # LVDS DDR bit clock
        self.dco_p = Signal()
        self.dco_n = Signal()

        # data (+frame) lanes
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)

        self.bitslip = Signal()        # Pulse to rotate

        # Idelay control input (on sys clock domain)
        # Only the dco_clock is adjustable
        self.id_inc = Signal()
        self.id_dec = Signal()
        self.id_value = Signal(5)
        # data is sampled in the middle of the eye, when
        # clk_data is sampled on the edge (appears jittery)
        self.clk_data = clk_data = Signal(8)

        # parallel data out, S-bit serdes on D-lanes (on sample clock domain)
        self.data_outs = [Signal(S) for i in range(D)]

        ###

        self.clock_domains.sample = ClockDomain("sample")   # recovered ADC sample clock
        self.io_clk = Signal()

        self.iserdes_default = {
            "p_DATA_WIDTH": S,
            "p_DATA_RATE": "DDR",
            "p_SERDES_MODE": "MASTER",
            "p_INTERFACE_TYPE": "NETWORKING",
            "p_NUM_CE": 1,

            "i_DDLY": 0,
            "i_CLK": self.io_clk,
            "i_CLKB": ~self.io_clk,
            "i_CLKDIV": ClockSignal("sample"),
            "i_CE1": 1,
            "i_CE2": 1,
            "i_DYNCLKDIVSEL": 0,
            "i_DYNCLKSEL": 0,
            "i_RST": ResetSignal("sys"),
            "i_BITSLIP": self.bitslip,
        }

        dco = Signal()
        dco_delay = Signal()
        id_CE = Signal()
        self.sync += id_CE.eq(self.id_inc ^ self.id_dec)
        self.specials += [
            DifferentialInput(self.dco_p, self.dco_n, dco),
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN",
                p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0,
                p_IDELAY_TYPE="VARIABLE",
                p_IDELAY_VALUE=6,

                i_C=ClockSignal("sys"),
                i_LD=ResetSignal("sys"),
                i_INC=self.id_inc,
                i_CE=id_CE,
                i_LDPIPEEN=0,
                i_CINVCTRL=0,
                i_CNTVALUEIN=Constant(0, 5),
                i_DATAIN=0,
                i_REGRST=0,
                i_IDATAIN=dco,

                o_DATAOUT=dco_delay,
                o_CNTVALUEOUT=self.id_value
            ),
            Instance("ISERDESE2",
                **self.iserdes_default,
                i_D=dco,
                o_Q1=clk_data[0],
                o_Q2=clk_data[1],
                o_Q3=clk_data[2],
                o_Q4=clk_data[3],
                o_Q5=clk_data[4],
                o_Q6=clk_data[5],
                o_Q7=clk_data[6],
                o_Q8=clk_data[7]
            ),
            Instance("BUFIO",
                i_I=dco_delay,
                o_O=self.io_clk
            ),
            Instance("BUFR",
                p_BUFR_DIVIDE=str(S),
                i_I=dco_delay,
                i_CE=1,
                i_CLR=0,
                o_O=ClockSignal("sample")
            )
        ]
        for i in range(D):
            dat = Signal()
            self.specials += DifferentialInput(
                self.lvds_data_p[i], self.lvds_data_n[i], dat
            )
            self.specials += Instance("ISERDESE2",
                **self.iserdes_default,
                i_D=dat,
                o_Q1=self.data_outs[i][0],
                o_Q2=self.data_outs[i][1],
                o_Q3=self.data_outs[i][2],
                o_Q4=self.data_outs[i][3],
                o_Q5=self.data_outs[i][4],
                o_Q6=self.data_outs[i][5],
                o_Q7=self.data_outs[i][6],
                o_Q8=self.data_outs[i][7]
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
            self.clk_data,
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
    d = S7_iserdes(S=8, D=1)
    convert(
        d,
        ios=d.getIOs(),
        special_overrides=xilinx_special_overrides,
        # create_clock_domains=False,
        name=tName
    ).write(tName + ".v")

