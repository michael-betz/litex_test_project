"""\
Spartan6 ISERDES receiver for LVDS ADCs

This is a rather uninformed mashup of
 * serdes_1_to_n_data_ddr_s8_diff.v
 * litevideo/datacapture.py

... you get what you pay for ;)

Migen can't handle the simulation of Xilinx hardware primitives
like PLL or IDELAY
hence this python file is only used to generate verilog code,
which is then simulated traditionally in iverilog.

try `python3 IserdesSp6.py build`
or `make view`
"""

from sys import argv, path, exit
from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from litex.soc.cores import frequency_meter
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BusSynchronizer
from migen.genlib.cdc import AsyncResetSynchronizer
from migen.genlib.misc import WaitTimer, timeline
path.append("..")
from general import *


class IserdesSp6(Module):
    def __init__(self, S=8, D=2, M=2, MIRROR_BITS=False, DCO_PERIOD=2.0):
        """
        Clock and data lanes must be in-phase (edge aligned)
        S = serialization factor (bits per frame)
        D = number of parallel lanes
        M = bits per DCO period per lane
        M = 1 for sdr, 2 for ddr, higher for a divided clock
        DCO_PERIOD [ns] for PLL_BASE

        data_outs[i] = parallel data of the i'th lvds lane

        MIRROR_BITS = False:
            first bit of the serial stream clocked in ends up in the
            LSB of data_outs

        Note: LTC2175 streams the MSB first and needs bit-mirroring
        """
        self.dco_p = Signal()          # LVDS clock
        self.dco_n = Signal()

        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)

        # Control signals (on sample clock domain)
        self.bitslip = Signal()        # Pulse to rotate
        self.pll_reset = Signal(reset=1)  # Reset PLL and `sample` clock domain

        # Phase detector readout (on sample clock domain)
        self.pd_int_period = Signal(32, reset=2**23)  # input for number of sample clock cycles to integrate
        self.pd_int_phases = [Signal((32, True)) for i in range(D)]  # outputs integrated Phase detector values (int32)
        self.id_auto_control = Signal()   # input to enable auto increment / decrement IDELAY based on PD value

        # Idelay control inputs (on sample clock domain)
        self.id_mux = Signal(max=D + 1)   # select a LVDS lane
        self.id_inc = Signal(1)
        self.id_dec = Signal(1)

        # parallel data out, S-bit serdes on D-lanes (on sample clock domain)
        self.data_outs = [Signal(S) for i in range(D)]
        self.clk_data_out = Signal(8)

        ###

        self.clock_domains.ioclock = ClockDomain()  # LVDS bit clock
        self.clock_domains.sample = ClockDomain()   # ADC sample clock

        # Sync resets
        self.pll_locked = Signal()
        self.specials += AsyncResetSynchronizer(self.sample, ~self.pll_locked)

        # -----------------------------
        #  IDELAY calibration
        # -----------------------------
        idelay_rst = Signal()
        idelay_cal_m = Signal()
        idelay_cal_s = Signal()
        idelay_busy = Signal()
        # High when IDELAY initialization complete
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
        # Periodically re-calibrate all slave IDELAY2s
        self.sync.sample += timeline(
            initial_tl_done,
            [
                (2**26, [idelay_cal_s.eq(1)])  # every 0.54 s at 125 MHz
            ]
        )

        idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_DATA_RATE": "SDR",
            "p_COUNTER_WRAPAROUND": "WRAPAROUND",
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
        self.specials += DifferentialInput(self.dco_p, self.dco_n, self.dco)
        dco_m = Signal()
        dco_s = Signal()
        self.specials += Instance(
            "IODELAY2",
            p_SERDES_MODE="MASTER",
            p_IDELAY_TYPE="VARIABLE_FROM_HALF_MAX",
            i_IDATAIN=self.dco,
            i_CAL=idelay_cal_m,
            i_CE=0,
            i_INC=0,
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
            i_CE=0,
            i_INC=0,
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

            i_RST=self.pll_reset,
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
            o_IOCLK=ClockSignal("ioclock"),
            # o_LOCK=,
            o_SERDESSTROBE=serdesstrobe
        )
        self.specials += Instance(
            "BUFG",
            i_I=pll_clk2,
            o_O=ClockSignal("sample")
        )

        # Accumulator regs for phase detector
        pd_int_accus = [Signal.like(s) for s in self.pd_int_phases]
        pd_int_cnt = Signal(32)
        self.sync.sample += [
            If(pd_int_cnt >= self.pd_int_period,
                pd_int_cnt.eq(0),
            ).Elif(initial_tl_done,     # only start counting when idelays are calibrated
                pd_int_cnt.eq(pd_int_cnt + 1)
            )
        ]

        # -----------------------------
        #  Data lanes with phase detector
        # -----------------------------
        for i in range(D):
            lvds_data = Signal()
            lvds_data_m = Signal()
            lvds_data_s = Signal()
            id_CE = Signal()
            id_INC = Signal()
            # -------------------------------------
            #  Idelay control (auto / manual)
            # -------------------------------------
            self.sync.sample += [
                # Mux the IDELAY control inputs
                If(self.id_auto_control,
                    id_CE.eq(
                        (pd_int_cnt == 1) &
                        # Adjust IDELAYS at end of each accumulator cycle
                        # (self.pd_int_phases[i] != 0)
                        # Adjust IDELAYs when consistently early / late
                        # during _all_ accumulator cycles
                        ((self.pd_int_phases[i] >= self.pd_int_period) |
                        (self.pd_int_phases[i] <= -self.pd_int_period))
                    ),
                    id_INC.eq(self.pd_int_phases[i] < 0)
                ).Else(
                    id_CE.eq((self.id_mux == i) & (self.id_inc ^ self.id_dec)),
                    id_INC.eq(self.id_inc)
                )
            ]
            self.specials += DifferentialInput(
                self.lvds_data_p[i], self.lvds_data_n[i], lvds_data
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="MASTER",
                p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                i_IDATAIN=lvds_data,
                i_CAL=idelay_cal_m,
                o_DATAOUT=lvds_data_m,
                i_CE=id_CE,
                i_INC=id_INC,
                **idelay_default
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="SLAVE",
                p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                i_IDATAIN=lvds_data,
                i_CAL=idelay_cal_s,
                o_DATAOUT=lvds_data_s,
                i_CE=id_CE,
                i_INC=id_INC,
                **idelay_default
            )
            cascade_up = Signal()
            cascade_down = Signal()
            tempData = Signal(8)
            pdValid = Signal()
            pdInc = Signal()
            pdAcc = pd_int_accus[i]
            self.specials += Instance(
                "ISERDES2",
                p_SERDES_MODE="MASTER",
                i_D=lvds_data_m,
                i_SHIFTIN=cascade_up,
                o_Q4=tempData[7],
                o_Q3=tempData[6],
                o_Q2=tempData[5],
                o_Q1=tempData[4],
                o_SHIFTOUT=cascade_down,
                # The phase detector outputs
                o_VALID=pdValid,
                o_INCDEC=pdInc,
                **iserdes_default
            )
            # Accumulate increment / decrement pulses
            self.sync.sample += [
                If(pd_int_cnt >= self.pd_int_period,
                    # Latch accumulator value into output registers
                    self.pd_int_phases[i].eq(pdAcc),
                    # Reset accumulators
                    pdAcc.eq(0)
                ).Elif(pdValid & initial_tl_done,
                    # Accumulate
                    If(pdInc,
                        pdAcc.eq(pdAcc - 1)
                    ).Else(
                        pdAcc.eq(pdAcc + 1)
                    )
                )
            ]
            self.specials += Instance(
                "ISERDES2",
                p_SERDES_MODE="SLAVE",
                i_D=lvds_data_s,
                i_SHIFTIN=cascade_down,
                o_Q4=tempData[3],
                o_Q3=tempData[2],
                o_Q2=tempData[1],
                o_Q1=tempData[0],
                o_SHIFTOUT=cascade_up,
                **iserdes_default
            )
            if MIRROR_BITS:
                self.comb += self.data_outs[i].eq(tempData[::-1])
            else:
                self.comb += self.data_outs[i].eq(tempData)


class LTCPhy(IserdesSp6, AutoCSR):
    """
    wire things up to CSRs
    this is done here to keep IserdesSp6 more or less simulate-able
    """
    def __init__(self, platform, f_enc):
        S = 8
        M = 8  # 8 DCO ticks during one frame tick
        D = 2
        DCO_PERIOD = 1 / (f_enc) * 1e9
        print("f_enc:", f_enc)
        print("DCO_PERIOD:", DCO_PERIOD)
        IserdesSp6.__init__(
            self, S=S, D=D, M=M, MIRROR_BITS=True, DCO_PERIOD=DCO_PERIOD
        )
        # pads_dco = platform.request("LTC_DCO")
        pads_frm = platform.request("LTC_FR")
        pads_chx = platform.request("LTC_OUT", 2)

        # CSRs for peeking at clock / data patterns
        self.data_peek = CSRStatus(16)
        self.specials += MultiReg(
            # LVDS_B (data_outs[1]) has the LSB and needs to come first!
            Cat(myzip(self.data_outs[1], self.data_outs[0])),
            self.data_peek.status
        )
        self.clk_peek = CSRStatus(8)
        self.specials += MultiReg(self.clk_data_out, self.clk_peek.status)

        # CSR for triggering bit-slip
        self.bitslip_csr = CSR(1)
        self.submodules.bs_sync = PulseSynchronizer("sys", "sample")

        # CSR to read phase detectors
        for i, phase_sample in enumerate(self.pd_int_phases):
            pd_phase_x = CSRStatus(32, name="pd_phase_{:d}".format(i))
            self.specials += MultiReg(phase_sample, pd_phase_x.status)
            setattr(self, "pd_phase_{:d}".format(i), pd_phase_x)

        # CSR for setting PD integration cycles
        self.pd_period_csr = CSRStorage(32, reset=2**20)
        # Not sure if MultiReg is really needed here?
        self.specials += MultiReg(
            self.pd_period_csr.storage, self.pd_int_period
        )

        # CSR for moving a IDELAY2 up / down
        self.idelay_auto = CSRStorage(1)
        self.idelay_mux = CSRStorage(8)
        self.idelay_inc = CSR(1)
        self.idelay_dec = CSR(1)
        self.submodules.idelay_inc_sync = PulseSynchronizer("sys", "sample")
        self.submodules.idelay_dec_sync = PulseSynchronizer("sys", "sample")
        self.specials += MultiReg(
            self.idelay_auto.storage, self.id_auto_control
        )
        self.specials += MultiReg(self.idelay_mux.storage, self.id_mux)

        # Frequency counter for sample clock
        self.submodules.f_sample = frequency_meter.FrequencyMeter(int(100e6))

        # Blinkies to see the clocks
        self.submodules.blinky_frm = LedBlinker(self.dco, f_enc)
        self.submodules.blinky_smpl = LedBlinker(ClockSignal("sample"), f_enc)

        self.comb += [
            self.f_sample.clk.eq(ClockSignal("sample")),
            # PLL does not lock when using the 500 MHz DDR DCO
            # self.dco_p.eq(pads_dco.p),
            # self.dco_n.eq(pads_dco.n),
            # (mis)using FRAME as /8 clock works fine and gives us a bitslip test-pattern
            self.dco_p.eq(pads_frm.p),
            self.dco_n.eq(pads_frm.n),
            self.lvds_data_p.eq(Cat(pads_chx.a_p, pads_chx.b_p)),
            self.lvds_data_n.eq(Cat(pads_chx.a_n, pads_chx.b_n)),
            self.bs_sync.i.eq(self.bitslip_csr.re),
            self.bitslip.eq(self.bs_sync.o),
            self.pll_reset.eq(ResetSignal("sys")),
            platform.request("user_led").eq(self.pll_reset),
            platform.request("user_led").eq(self.pll_locked),
            platform.request("user_led").eq(self.blinky_frm.out),
            platform.request("user_led").eq(self.blinky_smpl.out),
            self.idelay_inc_sync.i.eq(self.idelay_inc.re),
            self.idelay_dec_sync.i.eq(self.idelay_dec.re),
            self.id_inc.eq(self.idelay_inc_sync.o),
            self.id_dec.eq(self.idelay_dec_sync.o)
        ]


if __name__ == '__main__':
    if "build" not in argv:
        print(__doc__)
        exit(-1)
    from migen.fhdl.verilog import convert
    f_enc = 125e6
    S = 8
    DCO_PERIOD = 1 / (f_enc) * 1e9
    print("f_enc:", f_enc)
    print("DCO_PERIOD:", DCO_PERIOD)
    d = IserdesSp6(S=S, D=1, M=8, MIRROR_BITS=True, DCO_PERIOD=DCO_PERIOD)
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
            d.pd_int_period,
            d.id_auto_control,
            d.id_mux,
            d.id_inc,
            d.id_dec,
            d.clk_data_out,
            *d.pd_int_phases,
            *d.data_outs
        },
        special_overrides=xilinx_special_overrides,
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
