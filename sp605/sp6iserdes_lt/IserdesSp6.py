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
from migen.genlib.cdc import AsyncResetSynchronizer
from migen.genlib.misc import WaitTimer, timeline


class LedBlinker(Module):
    def __init__(self, clk_in, f_clk=100e6):
        """
        for debugging clocks
        toggles output at 1 Hz
        """
        self.out = Signal()

        ###

        self.clock_domains.cd_led = ClockDomain(reset_less=True)
        self.comb += self.cd_led.clk.eq(clk_in)
        max_cnt = int(f_clk // 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync.led += [
            If(cntr == (max_cnt),
                cntr.eq(0),
                self.out.eq(~self.out)
            ).Else(
                cntr.eq(cntr + 1)
            )
        ]


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
        self.pll_reset = Signal(reset=1)      # Reset PLL and `sample` clock domain

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
        self.dco = Signal()
        self.specials += Instance(
            "IBUFDS",
            i_I=self.dco_p,
            i_IB=self.dco_n,
            o_O=self.dco
        )
        dco_m = Signal()
        dco_s = Signal()
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="MASTER",
            p_IDELAY_TYPE="VARIABLE_FROM_HALF_MAX",
            i_IDATAIN=self.dco,
            i_CAL=idelay_cal_m,
            o_DATAOUT=dco_m,
            o_BUSY=idelay_busy,
            **idelay_default
        )
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="SLAVE",
            p_IDELAY_TYPE="FIXED",
            i_IDATAIN=self.dco,
            i_CAL=idelay_cal_m,
            o_DATAOUT=dco_s,
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
        self.pll_locked = Signal()

        clkfbout = Signal()

        self.specials += Instance(
            "PLL_ADV",
            name="PLL_IOCLOCK",
            p_SIM_DEVICE="SPARTAN6",
            p_CLKIN1_PERIOD=DCO_PERIOD,
            p_DIVCLK_DIVIDE=1,
            p_CLKFBOUT_MULT=M,
            p_CLKOUT0_DIVIDE=1,
            p_CLKOUT2_DIVIDE=S,
            # p_COMPENSATION="SOURCE_SYNCHRONOUS",
            p_COMPENSATION="INTERNAL",
            # p_CLK_FEEDBACK="CLKOUT0",

            i_RST=self.pll_reset,
            i_CLKINSEL=1,
            i_CLKIN1=pll_clkin,
            i_CLKIN2=0,
            # i_CLKFBIN=pll_clkfbin,
            o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,

            i_DADDR=0,
            i_DI=0,
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
    def __init__(self, platform, f_enc):
        S = 8
        DCO_PERIOD = 1 / (f_enc) * 1e9
        print("f_enc:", f_enc)
        print("DCO_PERIOD:", DCO_PERIOD)
        IserdesSp6.__init__(self, S=S, D=1, M=8, DCO_PERIOD=DCO_PERIOD)
        # pads_dco = platform.request("LTC_DCO")
        pads_frm = platform.request("LTC_FR")
        pads_chx = platform.request("LTC_OUT", 2)

        # ISE gets grumpy otherwise ...
        self.specials += Instance(
            "IBUFDS",
            i_I=pads_chx.b_p,
            i_IB=pads_chx.b_n,
            o_O=Signal()
        )

        # Sync resets
        self.specials += AsyncResetSynchronizer(self.sample, ~self.pll_locked)

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

        # Blinkies to see the clocks
        self.submodules.blinky_frm = LedBlinker(self.dco, f_enc)
        self.submodules.blinky_sample = LedBlinker(ClockSignal("sample"), f_enc)

        self.comb += [
            self.f_sample.clk.eq(ClockSignal("sample")),
            # self.dco_p.eq(pads_dco.p),
            # self.dco_n.eq(pads_dco.n),
            self.dco_p.eq(pads_frm.p),
            self.dco_n.eq(pads_frm.n),
            self.lvds_data_p.eq(pads_chx.a_p),
            self.lvds_data_n.eq(pads_chx.a_n),
            self.bs_sync.i.eq(self.bitslip_csr.re),
            self.bitslip.eq(self.bs_sync.o),
            self.pll_reset.eq(ResetSignal("sys")),
            platform.request("user_led").eq(self.pll_reset),
            platform.request("user_led").eq(self.pll_locked),
            platform.request("user_led").eq(self.blinky_frm.out),
            platform.request("user_led").eq(self.blinky_sample.out)
        ]


if __name__ == '__main__':
    from migen.fhdl.verilog import convert
    f_enc = 125e6
    S = 8
    DCO_PERIOD = 1 / (f_enc * S) * 1e9 * 2
    print("f_enc:", f_enc)
    print("DCO_PERIOD:", DCO_PERIOD)
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
            d.pll_reset,
            *d.data_outs
        },
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
