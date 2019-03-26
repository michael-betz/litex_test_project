# Spartan6 ISERDES receiver for LVDS ADCs
# This is a rather uninformed mashup of
#  * serdes_1_to_n_data_ddr_s8_diff.v
#  * litevideo/datacapture.py
# ... you get what you pay for
from migen import *
from litex.soc.interconnect.csr import *


class Sp6LvdsPhy(Module):
    def __init__(self, S=8, D=2):
        self.dco_p = Signal()          # DDR bit clock
        self.dco_n = Signal()
        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)
        # parallel data out, S-bit serdes on D-lanes
        self.data_outs = [Signal(S) for i in range(D)]
        self.clk_out = Signal()        # dat aout clock
        self.bitslip = Signal()        # Pulse to rotate

        ###

        self.specials += Instance(
            "IBUFDS_DIFF_OUT",
            i_I=self.dco_p,
            i_IB=self.dco_n,
            o_O=dcoo_p,
            o_OB=dcoo_n
        )
        ioclk_p = Signal()
        ioclk_n = Signal()
        idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_IDELAY_VALUE": 0,    # A faire: make CSR
            "p_IDELAY2_VALUE": 0,
            "p_ODELAY_VALUE": 0,
            "p_IDELAY_MODE": "NORMAL",
            "p_IDELAY_TYPE": "FIXED",
            "p_COUNTER_WRAPAROUND": "STAY_AT_LIMIT",
            "p_DELAY_SRC": "IDATAIN",
            "i_T": 1,
            "i_ODATAIN": 0,
            "i_IOCLK0": ioclk_p,
            "i_IOCLK1": ioclk_n,
            "i_CLK": 0,
            "i_CAL": 0,
            "i_INC": 0,
            "i_CE": 0,
            "i_RST": 0
        }
        self.special += Instance(
            "IODELAY2",
            p_DATA_RATE="SDR",
            p_SERDES_MODE="MASTER",
            i_IDATAIN=dcoo_p,
            o_DATAOUT=dco_del_p,
            **idelay_default
        )
        self.special += Instance(
            "IODELAY2",
            p_DATA_RATE="SDR",
            p_SERDES_MODE="SLAVE",
            i_IDATAIN=dcoo_n,
            o_DATAOUT=dco_del_n,
            **idelay_default
        )
        self.special += Instance(
            "BUFIO2_2CLK",
            p_DIVIDE=S,
            i_I=dco_del_p,
            i_IB=dco_del_n,
            o_IOCLK=ioclk_p,
            o_DIVCLK=divclk,
            o_SERDESSTROBE=serdesstrobe
        )
        self.special += Instance(
            "BUFIO2",
            p_I_INVERT="FASLE",
            p_DIVIDE_BYPASS="FALSE",
            p_USE_DOUBLER="FALSE",
            i_I=dco_del_n,
            o_IOCLK=ioclk_n
        )
        idelay_default["p_DATA_RATE"] = "DDR"
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
                p_DATA_RATE="DDR",
                p_SERDES_MODE="MASTER",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_m,
                **idelay_default
            )
            self.special += Instance(
                "IODELAY2",
                p_DATA_RATE="DDR",
                p_SERDES_MODE="SLAVE",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_s,
                **idelay_default
            )
            iserdes_default = {
                "p_DATA_WIDTH": S,
                "p_DATA_RATE": "DDR",
                "p_BITSLIP_ENABLE": "TRUE",
                "p_INTERFACE_TYPE": "RETIMED",
                "i_CE0": 1,
                "i_CLK0": ioclk_p,
                "i_CLK1": ioclk_n,
                "i_IOCE": serdesstrobe,
                "i_RST": ResetSignal(),
                "i_CLKDIV": ClockSignal(),
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
