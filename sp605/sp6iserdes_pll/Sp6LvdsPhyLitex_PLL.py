# Spartan6 ISERDES receiver for LVDS ADCs
# This is a rather uninformed mashup of
#  * serdes_1_to_n_data_ddr_s8_diff.v
#  * litevideo/datacapture.py
# ... you get what you pay for
from migen import *
from litex.soc.interconnect.csr import *


class Sp6LvdsPhy(Module):
    def __init__(self, S=8, D=2):
        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)
        # parallel data out, S-bit serdes on D-lanes
        self.data_outs = [Signal(S) for i in range(D)]
        self.clk_out = Signal()        # dat aout clock
        self.bitslip = Signal()        # Pulse to rotate

        ###

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
            self.special += Instance(
                "IBUFDS",
                i_I=self.lvds_data_p[i],
                i_IB=self.lvds_data_n[i],
                o_O=lvds_data
            )
            self.special += Instance(
                "IODELAY2",
                p_SERDES_MODE="MASTER",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_m,
                **idelay_default
            )
            self.special += Instance(
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
            self.special += Instance(
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
            self.special += Instance(
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
