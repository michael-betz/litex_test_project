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
from litex.soc.cores import frequency_meter
from migen.build.xilinx import XilinxPlatform
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BusSynchronizer
from migen.genlib.misc import WaitTimer, timeline


def myzip(*vals):
    return [i for t in zip(*vals) for i in t]


class IserdesSp6(Module):
    def __init__(self, S=8, D=2, M=2, DCO_PERIOD=2.0):
        """
        S = serialization factor (bits per frame)
        D = number of parallel lanes
        M = bits per DCO period per lane
        M = 1 for sdr, 2 for ddr, higher for a divided clock
        DCO_PERIOD [ns] for PLL_BASE
        """
        self.dco_p = Signal()      # LVDS clock
        self.dco_n = Signal()

        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)

        # Control signals (on sample clock domain)
        self.bitslip = Signal()        # Pulse to rotate

        # parallel data out, S-bit serdes on D-lanes
        self.data_outs = [Signal(S) for i in range(D)]
        self.clk_data_out = Signal(8)

        ###

        self.clock_domains.ioclock = ClockDomain()  # LVDS bit clock
        self.clock_domains.sample = ClockDomain()   # ADC sample clock


        # -----------------------------
        #  IDELAY calibration
        # -----------------------------
        idelay_rst = Signal()
        idelay_cal_m = Signal()
        idelay_cal_s = Signal()
        idelay_busy = Signal()
        initial_tl_done = Signal()
        self.sync.sample += [
            idelay_cal_m.eq(0),
            idelay_cal_s.eq(0),
            idelay_rst.eq(0)
        ]
        # Initially calibrate and reset all IDELAY2s
        self.sync.sample += timeline(
            ~(idelay_busy | initial_tl_done),
            [
                (20, [idelay_cal_m.eq(1), idelay_cal_s.eq(1)]),
                (40, [idelay_rst.eq(1)]),
                (50, [initial_tl_done.eq(1)])
            ]
        )
        # Periodically re-calibrate slave IDELAY2s
        self.sync.sample += timeline(
            initial_tl_done,
            [
                (2**16, [idelay_cal_s.eq(1)])
            ]
        )

        idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_DATA_RATE": "SDR",
            "p_IDELAY_VALUE": 0,
            "p_IDELAY2_VALUE": 0,
            "p_ODELAY_VALUE": 0,
            "p_IDELAY_MODE": "NORMAL",
            "p_DELAY_SRC": "IDATAIN",
            "i_T": 1,
            "i_ODATAIN": 0,
            "i_IOCLK0": ClockSignal("ioclock"),
            "i_IOCLK1": 0,
            "i_CLK": ClockSignal("sample"),
             # A faire: wire these up
            "i_INC": 0,
            "i_CE": 0,
            "i_RST": idelay_rst
        }

        serdesstrobe = Signal()
        iserdes_default = {
            "p_DATA_WIDTH": S,
            "p_DATA_RATE": "SDR",
            "p_BITSLIP_ENABLE": "TRUE",
            "p_INTERFACE_TYPE": "RETIMED",
            "i_CE0": 1,
            "i_CLK0": ClockSignal("ioclock"),
            "i_CLK1": 0,
            "i_IOCE": serdesstrobe,
            "i_RST": ~initial_tl_done,
            "i_CLKDIV": ClockSignal("sample"),
            "i_BITSLIP": self.bitslip
        }

        # -----------------------------
        #  Generate clocks
        # -----------------------------
        dco = Signal()
        self.specials += Instance(
            "IBUFDS",
            i_I=self.dco_p,
            i_IB=self.dco_n,
            o_O=dco
        )
        dco_m = Signal()
        dco_s = Signal()
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="MASTER",
            p_IDELAY_TYPE="FIXED",
            i_IDATAIN=dco,
            i_CAL=idelay_cal_m,
            o_DATAOUT=dco_m,
            o_BUSY=idelay_busy,
            **idelay_default
        )
        idel_busy = Signal()
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="SLAVE",
            p_IDELAY_TYPE="VARIABLE_FROM_HALF_MAX",
            i_IDATAIN=dco,
            o_DATAOUT=dco_s,
            i_CAL=idelay_cal_m,
            o_BUSY=idel_busy,

            **idelay_default
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
            **iserdes_default
        )
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
            **iserdes_default
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
        pll_locked = Signal()
        self.specials += Instance(
            "PLL_BASE",
            p_CLKIN_PERIOD=DCO_PERIOD,
            p_DIVCLK_DIVIDE=1,
            p_CLKFBOUT_MULT=M,
            p_CLKOUT0_DIVIDE=1,
            p_CLKOUT2_DIVIDE=S,
            p_COMPENSATION="SOURCE_SYNCHRONOUS",
            p_CLK_FEEDBACK="CLKOUT0",
            i_RST=ResetSignal("sample"),
            i_CLKIN=pll_clkin,
            i_CLKFBIN=pll_clkfbin,
            o_CLKOUT0=pll_clk0,
            o_CLKOUT2=pll_clk2,
            o_LOCKED=pll_locked
        )
        self.specials += Instance(
            "BUFPLL",
            p_DIVIDE=S,
            i_PLLIN=pll_clk0,
            i_GCLK=ClockSignal("sample"),
            i_LOCKED=pll_locked,
            o_IOCLK=ClockSignal("ioclock"),
            # o_LOCK=,
            o_SERDESSTROBE=serdesstrobe
        )
        self.specials += Instance(
            "BUFG",
            i_I=pll_clk2,
            o_O=ClockSignal("sample")
        )

        # -----------------------------
        #  Data lanes
        # -----------------------------
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
                p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                p_COUNTER_WRAPAROUND="WRAPAROUND",
                i_IDATAIN=lvds_data,
                i_CAL=idelay_cal_m,
                o_DATAOUT=lvds_data_m,
                **idelay_default
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="SLAVE",
                p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                p_COUNTER_WRAPAROUND="WRAPAROUND",
                i_IDATAIN=lvds_data,
                i_CAL=idelay_cal_s,
                o_DATAOUT=lvds_data_s,
                **idelay_default
            )
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


class LTCPhy(IserdesSp6, AutoCSR):
    """
    wire things up to CSRs
    this is done here to keep IserdesSp6 easily simulateable
    """
    def __init__(self, platform):
        IserdesSp6.__init__(self, S=8, D=1, M=2, DCO_PERIOD=2.0)
        pads_dco = platform.request("LTC_DCO")
        pads_chx = platform.request("LTC_OUT", 2)
        # ISE gets grumpy otherwise ...
        self.specials += Instance(
            "IBUFDS",
            i_I=pads_chx.b_p,
            i_IB=pads_chx.b_n,
            o_O=Signal()
        )
        # CSRs for peeking at clock / data patterns
        self.data_peek = CSRStatus(8)
        self.specials += MultiReg(
            self.data_outs[0],
            self.data_peek.status
        )
        self.clk_peek = CSRStatus(8)
        self.specials += MultiReg(
            self.clk_data_out,
            self.clk_peek.status
        )
        # CSR for triggering bit-slip
        self.bitslip_csr = CSR(1)
        self.submodules.bs_sync = PulseSynchronizer("sys", "sample")
        # Frequency counter for sample clock
        self.submodules.f_sample = frequency_meter.FrequencyMeter(int(100e6))
        self.comb += [
            self.f_sample.clk.eq(ClockSignal("sample")),
            self.dco_p.eq(pads_dco.p),
            self.dco_n.eq(pads_dco.n),
            self.lvds_data_p.eq(pads_chx.a_p),
            self.lvds_data_n.eq(pads_chx.a_n),
            self.bs_sync.i.eq(self.bitslip_csr.re),
            self.bitslip.eq(self.bs_sync.o)
        ]


if __name__ == '__main__':
    from migen.fhdl.verilog import convert
    S = 8
    DCO_PERIOD = 1 / (125e6 * S) * 1e9 * 2
    d = IserdesSp6(S=S, D=1, M=2, DCO_PERIOD=DCO_PERIOD)
    convert(
        d,
        ios={
            d.dco_p,
            d.dco_n,
            d.ioclock.clk,
            d.sample.clk,
            d.bitslip,
            d.lvds_data_p,
            d.lvds_data_n,
            *d.data_outs
        },
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
