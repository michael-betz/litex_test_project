"""\
 7-series ISERDES receiver for LVDS ADCs

 Needs a DDR clock signal, doing one transition for every bit

 Untested so far

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

        self.rx_p = Signal()
        self.rx_n = Signal()

        # Control
        self.delay_rst = Signal()
        self.delay_inc = Signal()

        ###

        # Add data lanes and control signals
        data_nodelay = Signal()
        self.data_delayed = data_delayed = Signal()
        self.specials += [
            DifferentialInput(self.rx_p, self.rx_n, data_nodelay),
            Instance("IDELAYE2",
                p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE",
                p_REFCLK_FREQUENCY=200.0, p_PIPE_SEL="FALSE",
                p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=0,

                i_C=ClockSignal(),
                i_LD=self.delay_rst,
                i_CE=self.delay_inc,
                i_LDPIPEEN=0, i_INC=1,

                i_IDATAIN=data_nodelay, o_DATAOUT=data_delayed
            ),
            Instance("ISERDESE2",
                p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1, p_IOBDELAY="IFD",

                i_DDLY=data_delayed,
                i_CE1=1,
                i_RST=ResetSignal("sys"),
                i_CLK=ClockSignal("sys4x"), i_CLKB=~ClockSignal("sys4x"),
                i_CLKDIV=ClockSignal("sys"),
                i_BITSLIP=0,
                o_Q8=data_deserialized[0], o_Q7=data_deserialized[1],
                o_Q6=data_deserialized[2], o_Q5=data_deserialized[3],
                o_Q4=data_deserialized[4], o_Q3=data_deserialized[5],
                o_Q2=data_deserialized[6], o_Q1=data_deserialized[7]
            )
        ]

    def getIOs(self):
        """ for easier interfacing to testbench """
        return {self.rx_p, self.rx_n, self.data_delayed}


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

