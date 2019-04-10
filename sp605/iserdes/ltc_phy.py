from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from litex.soc.cores import frequency_meter
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc
from sp6_pll import Sp6PLL
# from sp6_ddr import Sp6DDR


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]


class LedBlinker(Module):
    def __init__(self, f_clk=100e6):
        """
        for debugging clocks
        toggles output at 1 Hz
        use ClockDomainsRenamer()!
        """
        self.out = Signal()

        ###

        max_cnt = int(f_clk // 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync += [
            cntr.eq(cntr + 1),
            If(cntr == max_cnt,
                cntr.eq(0),
                self.out.eq(~self.out)
            )
        ]


class LTCPhy(Sp6PLL, AutoCSR):
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
        ),
        # Connect GPIO_SMA on SP605 with CLK input on 1525A
        # Alternatively, use a Si570 eval board as clock source
        ("ENC_CLK", 0,
            Subsignal("p", Pins("SMA_GPIO:P")),
            Subsignal("n", Pins("SMA_GPIO:N")),
            # Note: the LTC eval board needs to be modded
            # to accept a differential clock
            IOStandard("LVDS_25")
        )
    ]

    def __init__(self, platform, f_enc):
        S = 8
        M = 8  # 8 DCO ticks during one frame tick
        D = 2
        DCO_PERIOD = 1 / (f_enc) * 1e9
        print("f_enc:", f_enc)
        print("DCO_PERIOD:", DCO_PERIOD)
        # Note: LTC2175 streams the MSB first and needs bit-mirroring
        Sp6PLL.__init__(
            self, S=S, D=D, M=M, MIRROR_BITS=True,
            DCO_PERIOD=DCO_PERIOD, CLK_EDGE_ALIGNED=True,
            BITSLIPS=2
        )

        # pads_dco = platform.request("LTC_DCO")
        pads_frm = platform.request("LTC_FR")
        pads_chx = platform.request("LTC_OUT", 2)

        # CSRs for peeking at clock / data patterns
        self.sample_out = Signal(16)
        # LVDS_B (data_outs[1]) has the LSB and needs to come first!
        self.comb += self.sample_out.eq(
            Cat(myzip(self.data_outs[1], self.data_outs[0]))
        )
        self.data_peek = CSRStatus(16)
        self.specials += MultiReg(
            self.sample_out,
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
        self.submodules.blinky_smpl = ClockDomainsRenamer("sample")(
            LedBlinker(f_enc)
        )

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
            self.reset.eq(ResetSignal("sys")),
            platform.request("user_led").eq(self.reset),
            platform.request("user_led").eq(self.pll_locked),
            platform.request("user_led").eq(self.blinky_smpl.out),
            self.idelay_inc_sync.i.eq(self.idelay_inc.re),
            self.idelay_dec_sync.i.eq(self.idelay_dec.re),
            self.id_inc.eq(self.idelay_inc_sync.o),
            self.id_dec.eq(self.idelay_dec_sync.o)
        ]
