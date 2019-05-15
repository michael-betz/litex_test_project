from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from litex.soc.cores import frequency_meter
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc
from sys import path
path.append("..")
from common import LedBlinker


class LTCPhy(Module, AutoCSR):
    """
    wire things up to CSRs
    this is done here to keep sp6_* more or less simulate-able
    """
    pads = [
        ("LTC_SPI", 0,
            Subsignal("cs_n", Pins("LPC:LA14_P")),
            Subsignal("miso", Pins("LPC:LA14_N"), Misc("PULLUP")),
            Subsignal("mosi", Pins("LPC:LA27_P")),
            Subsignal("clk",  Pins("LPC:LA27_N")),
            IOStandard("LVCMOS25")
        ),
        ("LTC_OUT", 0,  # Bank 0
            Subsignal("a_p", Pins("LPC:LA03_P")),
            Subsignal("a_n", Pins("LPC:LA03_N")),
            Subsignal("b_p", Pins("LPC:LA08_P")),
            Subsignal("b_n", Pins("LPC:LA08_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        ),
        ("LTC_OUT", 1,  # Bank 0
            Subsignal("a_p", Pins("LPC:LA12_P")),
            Subsignal("a_n", Pins("LPC:LA12_N")),
            Subsignal("b_p", Pins("LPC:LA16_P")),
            Subsignal("b_n", Pins("LPC:LA16_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        ),
        ("LTC_OUT", 2,  # Bank 2
            Subsignal("a_p", Pins("LPC:LA22_P")),
            Subsignal("a_n", Pins("LPC:LA22_N")),
            Subsignal("b_p", Pins("LPC:LA25_P")),
            Subsignal("b_n", Pins("LPC:LA25_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        ),
        ("LTC_OUT", 3,  # Bank 2
            Subsignal("a_p", Pins("LPC:LA29_P")),
            Subsignal("a_n", Pins("LPC:LA29_N")),
            Subsignal("b_p", Pins("LPC:LA31_P")),
            Subsignal("b_n", Pins("LPC:LA31_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        ),
        ("LTC_FR", 0,  # Bank 2
            Subsignal("p", Pins("LPC:LA18_CC_P")),
            Subsignal("n", Pins("LPC:LA18_CC_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        ),
        ("LTC_DCO", 0,  # Bank 2
            Subsignal("p", Pins("LPC:LA17_CC_P")),
            Subsignal("n", Pins("LPC:LA17_CC_N")),
            IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")
        )
    ]

    def __init__(self, platform, f_enc):
        S = 8
        M = 8  # 8 DCO ticks during one frame tick
        D = 2
        DCO_PERIOD = 1 / (f_enc) * 1e9
        print("f_enc:", f_enc, "DCO_PERIOD:", DCO_PERIOD)
        # Note: LTC2175 streams the MSB first and needs bit-mirroring
        # Sp6PLL.__init__(
        #     self, S=S, D=D, M=M, MIRROR_BITS=True,
        #     DCO_PERIOD=DCO_PERIOD, CLK_EDGE_ALIGNED=True,
        #     BITSLIPS=2
        # )

        # pads_dco = platform.request("LTC_DCO")
        pads_frm = platform.request("LTC_FR")
        # pads_chx = platform.request("LTC_OUT", 2)

        # CSRs for peeking at clock / data patterns
        # self.sample_out = Signal(16)
        # LVDS_B (data_outs[1]) has the LSB and needs to come first!
        # self.comb += self.sample_out.eq(
        #     Cat(myzip(self.data_outs[1], self.data_outs[0]))
        # )
        # self.data_peek = CSRStatus(16)
        # self.specials += MultiReg(
        #     self.sample_out,
        #     self.data_peek.status
        # )
        # self.clk_peek = CSRStatus(8)
        # self.specials += MultiReg(self.clk_data_out, self.clk_peek.status)

        # CSR for triggering bit-slip
        # self.bitslip_csr = CSR(1)
        # self.submodules.bs_sync = PulseSynchronizer("sys", "sample")

        # CSR to read phase detectors
        # for i, phase_sample in enumerate(self.pd_int_phases):
        #     pd_phase_x = CSRStatus(32, name="pd_phase_{:d}".format(i))
        #     self.specials += MultiReg(phase_sample, pd_phase_x.status)
        #     setattr(self, "pd_phase_{:d}".format(i), pd_phase_x)

        # CSR for setting PD integration cycles
        # self.pd_period_csr = CSRStorage(32, reset=2**20)
        # Not sure if MultiReg is really needed here?
        # self.specials += MultiReg(
        #     self.pd_period_csr.storage, self.pd_int_period
        # )

        # CSR for moving a IDELAY2 up / down
        # self.idelay_auto = CSRStorage(1)
        # self.idelay_mux = CSRStorage(8)
        # self.idelay_inc = CSR(1)
        # self.idelay_dec = CSR(1)
        # self.submodules.idelay_inc_sync = PulseSynchronizer("sys", "sample")
        # self.submodules.idelay_dec_sync = PulseSynchronizer("sys", "sample")
        # self.specials += MultiReg(
        #     self.idelay_auto.storage, self.id_auto_control
        # )
        # self.specials += MultiReg(self.idelay_mux.storage, self.id_mux)

        # Frequency counter / blinkie for received sample clock
        self.submodules.f_frame = frequency_meter.FrequencyMeter(int(125e6))
        self.specials += DifferentialInput(
            pads_frm.p, pads_frm.n, self.f_frame.clk
        )
        # Blinkies to see the clocks
        self.clock_domains.frame = ClockDomain("frame")
        self.submodules.blinky_frame = ClockDomainsRenamer("frame")(
            LedBlinker(f_enc)
        )
        self.comb += [
            ClockSignal("frame").eq(self.f_frame.clk),
            platform.request("user_led").eq(self.blinky_frame.out)
        ]
