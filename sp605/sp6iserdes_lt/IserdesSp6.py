# Spartan6 ISERDES receiver for LVDS ADCs
# This is a rather uninformed mashup of
#
#  * serdes_1_to_n_data_ddr_s8_diff.v
#  * litevideo/datacapture.py
#
# ... you get what you pay for ;)
#
# Migen can't handle the simulation of Xilinx hardware primitives
# like PLL or IDELAY
# hence this python file is only used to generate verilog code,
# which is then simulated traditionally in iverilog.
# Try `make view`

from sys import argv
from migen import *
from litex.soc.interconnect.csr import *
from migen.build.xilinx import XilinxPlatform


class IserdesSp6(Module):
    def __init__(self, DCO_PERIOD, S=8, D=2, M=2):
        """
        S = serialization factor
        D = number of parallel lanes
        M=1 for sdr, 2 for ddr, N for divide by N LVDS clock
        """
        self.dco_p = Signal()      # DDR pixel clock
        self.dco_n = Signal()

        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)

        # parallel data out, S-bit serdes on D-lanes
        self.data_outs = [Signal(S) for i in range(D)]
        self.bitslip = Signal()        # Pulse to rotate

        self.clock_domains.dco2x = ClockDomain()   # LVDS bit clock
        self.clock_domains.sample = ClockDomain()  # ADC sample clock

        ###

        # -----------------------------
        #  Generate clocks
        # -----------------------------
        serdesstrobe = Signal()
        dco = Signal()
        self.specials += Instance(
            "IBUFDS",
            i_I=self.dco_p,
            i_IB=self.dco_n,
            o_O=dco
        )
        clkfbout = Signal()
        pll_locked = Signal()
        pll_clk0 = Signal()
        pll_clk1 = Signal()
        self.specials += Instance(
            "PLL_BASE",
            p_CLKIN_PERIOD=DCO_PERIOD,
            p_CLKFBOUT_MULT=M,
            p_CLKOUT0_DIVIDE=1,
            p_CLKOUT1_DIVIDE=S,
            p_COMPENSATION="SOURCE_SYNCHRONOUS",
            p_CLK_FEEDBACK="CLKOUT0",

            i_RST=0,
            i_CLKIN=dco,
            i_CLKFBIN=clkfbout,

            o_CLKFBOUT=clkfbout,
            o_CLKOUT0=pll_clk0,
            o_CLKOUT1=pll_clk1,
            o_LOCKED=pll_locked
        )
        self.specials += Instance(
            "BUFG",
            i_I=pll_clk1,
            o_O=ClockSignal("sample")
        )

        locked_async = Signal()
        self.specials += Instance(
            "BUFPLL",
            p_DIVIDE=S,
            i_PLLIN=pll_clk0,
            i_GCLK=ClockSignal("sample"),
            i_LOCKED=pll_locked,
            o_IOCLK=ClockSignal("dco2x"),
            o_LOCK=locked_async,
            o_SERDESSTROBE=serdesstrobe
        )

        # -----------------------------
        #  Data lanes
        # -----------------------------
        idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_DATA_RATE": "SDR",
            "p_IDELAY_VALUE": 0,
            "p_IDELAY2_VALUE": 0,
            "p_ODELAY_VALUE": 0,
            "p_IDELAY_MODE": "NORMAL",
            "p_IDELAY_TYPE": "DIFF_PHASE_DETECTOR",
            "p_COUNTER_WRAPAROUND": "WRAPAROUND",
            "p_DELAY_SRC": "IDATAIN",
            "i_T": 1,
            "i_ODATAIN": 0,
            "i_IOCLK0": ClockSignal("dco2x"),
            "i_IOCLK1": 0,
            "i_CLK": ClockSignal("sample"),
             # A faire: wire these up
            "i_CAL": 0,
            "i_INC": 0,
            "i_CE": 0,
            "i_RST": 0,
            # "o_BUSY":
        }

        for i in range(D):
            lvds_data = Signal()
            lvds_data_m = Signal()
            lvds_data_s = Signal()
            self.specials += Instance(
                "IBUFDS",
                i_I=self.lvds_data_p[i],
                i_IB=self.lvds_data_n[i],
                o_O=lvds_data
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="MASTER",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_m,
                **idelay_default
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="SLAVE",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_s,
                **idelay_default
            )
            iserdes_default = {
                "p_DATA_WIDTH": S,
                "p_DATA_RATE": "SDR",
                "p_BITSLIP_ENABLE": "TRUE",
                "p_INTERFACE_TYPE": "RETIMED",
                "i_CE0": 1,
                "i_CLK0": ClockSignal("dco2x"),
                "i_CLK1": 0,
                "i_IOCE": serdesstrobe,
                "i_RST": ResetSignal("sample"),
                "i_CLKDIV": ClockSignal("sample"),
                "i_BITSLIP": self.bitslip
            }
            cascade_up = Signal()
            cascade_down = Signal()
            self.specials += Instance(
                "ISERDES2",
                p_SERDES_MODE="MASTER",
                i_D=lvds_data_m,
                i_SHIFTIN=cascade_up,
                o_Q4=self.data_outs[i][7],
                o_Q3=self.data_outs[i][6],
                o_Q2=self.data_outs[i][5],
                o_Q1=self.data_outs[i][4],
                o_SHIFTOUT=cascade_down,
                **iserdes_default
            )
            self.specials += Instance(
                "ISERDES2",
                p_SERDES_MODE="SLAVE",
                i_D=lvds_data_s,
                i_SHIFTIN=cascade_down,
                o_Q4=self.data_outs[i][3],
                o_Q3=self.data_outs[i][2],
                o_Q2=self.data_outs[i][1],
                o_Q1=self.data_outs[i][0],
                o_SHIFTOUT=cascade_up,
                **iserdes_default
            )


if __name__ == '__main__':
    from migen.fhdl.verilog import convert
    S = 8
    DCO_PERIOD = 1 / (125e6 * S) * 1e9 * 2
    d = IserdesSp6(DCO_PERIOD, S)
    convert(
        d,
        ios={
            d.dco_p,
            d.dco_n,
            d.dco2x.clk,
            d.sample.clk,
            d.bitslip,
            d.lvds_data_p,
            d.lvds_data_n,
            *d.data_outs
        },
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
