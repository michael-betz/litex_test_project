from sys import argv
from migen import *
from migen.genlib.io import DifferentialInput
from migen.build.xilinx.common import xilinx_special_overrides
from migen.genlib.misc import WaitTimer, timeline


class Sp6Common(Module):
    def __init__(
        self, S, D, MIRROR_BITS, BITSLIPS,
        idelay_overrides={}, iserdes_overrides={}
    ):
        """
        Generates all logic necessary for the data lanes, calibration
        and phase detection / adjustment
        Does not do anything related to clocking.
        Inherit and add you own clock.
        """
        # LVDS DDR bit clock
        self.dco_p = Signal()
        self.dco_n = Signal()

        # data lanes
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)

        # Control signals (on sample clock domain)
        self.bitslip = Signal()        # Pulse to rotate

        # Phase detector readout (on sample clock domain)
        # input for number of sample clock cycles to integrate
        self.pd_int_period = Signal(32, reset=2**23)
        # outputs integrated Phase detector values (int32)
        self.pd_int_phases = [Signal((32, True)) for i in range(D)]
        # input to enable auto increment / decrement IDELAY based on PD value
        self.id_auto_control = Signal()

        # Idelay control inputs (on sample clock domain)
        self.id_mux = Signal(max=D + 1)   # select a LVDS lane
        self.id_inc = Signal(1)
        self.id_dec = Signal(1)

        # parallel data out, S-bit serdes on D-lanes (on sample clock domain)
        self.data_outs = [Signal(S) for i in range(D)]

        # Async Reset for clock generation and `sample` clock domain
        self.reset = Signal(reset=1)

        ###

        # Common internal signals which must be driven by child
        self.clock_domains.sample = ClockDomain("sample")   # ADC sample clock
        self.ioclk_p = Signal()
        self.ioclk_n = Signal()
        self.serdesstrobe = Signal()

        # -----------------------------
        #  IDELAY calibration
        # -----------------------------
        self.idelay_rst = Signal()
        self.idelay_cal_m = Signal()
        self.idelay_cal_s = Signal()
        # High when IDELAY initialization complete
        self.initial_tl_done = Signal()
        bitslip_initial = Signal()
        self.sync.sample += [
            self.idelay_cal_m.eq(0),
            self.idelay_cal_s.eq(0),
            self.idelay_rst.eq(0),
            bitslip_initial.eq(0)
        ]
        # Initially calibrate and reset all IDELAY2s
        tl = [
            (20, [self.idelay_cal_m.eq(1), self.idelay_cal_s.eq(1)]),
            (40, [self.idelay_rst.eq(1)]),
            (60, [self.initial_tl_done.eq(1)]),
            # Add initial bitslips starting from clk 100. Have I gone too far?
            *zip(
                [100 + i * 10 for i in range(BITSLIPS)],
                [[bitslip_initial.eq(1)]] * BITSLIPS
            )
        ]
        # print(tl)
        self.sync.sample += timeline(~self.initial_tl_done, tl)
        # Periodically re-calibrate all slave IDELAY2s
        self.sync.sample += timeline(
            self.initial_tl_done,
            [
                (2**26, [self.idelay_cal_s.eq(1)])  # every 0.54 s at 125 MHz
            ]
        )

        # Accumulator regs for phase detector
        pd_int_accus = [Signal.like(s) for s in self.pd_int_phases]
        pd_int_cnt = Signal(32)
        self.sync.sample += [
            If(pd_int_cnt >= self.pd_int_period,
                pd_int_cnt.eq(0),
            ).Elif(self.initial_tl_done,     # only start counting when idelays are calibrated
                pd_int_cnt.eq(pd_int_cnt + 1)
            )
        ]

        # -----------------------------
        #  Default block parameters
        # -----------------------------
        self.idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_IDELAY_VALUE": 0,    # A faire: make CSR
            "p_IDELAY2_VALUE": 0,
            "p_ODELAY_VALUE": 0,
            "p_IDELAY_MODE": "NORMAL",
            "p_COUNTER_WRAPAROUND": "WRAPAROUND",
            "p_DELAY_SRC": "IDATAIN",
            "i_T": 1,
            "i_ODATAIN": 0,
            "i_IOCLK0": self.ioclk_p,
            "i_IOCLK1": self.ioclk_n,
            "i_CLK": ClockSignal("sample"),
            "i_RST": self.idelay_rst
        }
        self.idelay_default.update(idelay_overrides)
        self.iserdes_default = {
            "p_DATA_WIDTH": S,
            "p_BITSLIP_ENABLE": "TRUE",
            "p_INTERFACE_TYPE": "RETIMED",
            "i_CE0": 1,
            "i_CLK0": self.ioclk_p,
            "i_CLK1": self.ioclk_n,
            "i_IOCE": self.serdesstrobe,
            "i_RST": ~self.initial_tl_done,
            "i_CLKDIV": ClockSignal("sample"),
            "i_BITSLIP": self.bitslip | bitslip_initial
        }
        self.iserdes_default.update(iserdes_overrides)

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
                        (self.pd_int_phases[i] != 0)
                        # Adjust IDELAYs when consistently early / late
                        # during _all_ accumulator cycles
                        # ((self.pd_int_phases[i] >= self.pd_int_period) |
                        # (self.pd_int_phases[i] <= -self.pd_int_period))
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
                i_CAL=self.idelay_cal_m,
                i_CE=id_CE,
                i_INC=id_INC,
                o_DATAOUT=lvds_data_m,
                **self.idelay_default
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="SLAVE",
                p_IDELAY_TYPE="DIFF_PHASE_DETECTOR",
                i_IDATAIN=lvds_data,
                i_CAL=self.idelay_cal_s,
                i_CE=id_CE,
                i_INC=id_INC,
                o_DATAOUT=lvds_data_s,
                **self.idelay_default
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
                **self.iserdes_default
            )
            # Accumulate increment / decrement pulses
            self.sync.sample += [
                If(pd_int_cnt >= self.pd_int_period,
                    # Latch accumulator value into output registers
                    self.pd_int_phases[i].eq(pdAcc),
                    # Reset accumulators
                    pdAcc.eq(0)
                ).Elif(pdValid & self.initial_tl_done,
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
                **self.iserdes_default
            )
            if MIRROR_BITS:
                self.comb += self.data_outs[i].eq(tempData[::-1])
            else:
                self.comb += self.data_outs[i].eq(tempData)

    def getIOs(self):
        """ for easier interfacing to testbench """
        return {
            self.dco_p,
            self.dco_n,
            self.sample.clk,
            self.bitslip,
            self.lvds_data_p,
            self.lvds_data_n,
            self.pd_int_period,
            self.id_auto_control,
            self.id_mux,
            self.id_inc,
            self.id_dec,
            self.reset,
            *self.pd_int_phases,
            *self.data_outs
        }
