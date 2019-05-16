from migen import *
from migen.build.xilinx.common import *
from litex.soc.interconnect.csr import *
from litex.soc.cores import frequency_meter
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc
from sys import path
from s7_iserdes import S7_iserdes
path.append("..")
from common import LedBlinker, myzip


class LTCPhy(S7_iserdes, AutoCSR):
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
        D = 3
        DCO_PERIOD = 1 / (f_enc) * 1e9
        print("f_enc:", f_enc, "DCO_PERIOD:", DCO_PERIOD)
        # Note: LTC2175 streams the MSB first and needs bit-mirroring
        S7_iserdes.__init__(self, S=S, D=D)

        pads_dco = platform.request("LTC_DCO")
        self.comb += [
            self.dco_p.eq(pads_dco.p),
            self.dco_n.eq(pads_dco.n)
        ]

        pads_out = platform.request("LTC_OUT", 0)
        pads_frm = platform.request("LTC_FR")
        self.comb += [
            self.lvds_data_p.eq(Cat(pads_out.a_p, pads_out.b_p, pads_frm.p)),
            self.lvds_data_n.eq(Cat(pads_out.a_n, pads_out.b_n, pads_frm.n))
        ]

        # CSRs for peeking at data pattern
        self.sample_out = Signal(S * 2)
        # LVDS_B (data_outs[1]) has the LSB and needs to come first!
        self.comb += self.sample_out.eq(
            Cat(myzip(self.data_outs[1], self.data_outs[0]))
        )
        self.data_peek = CSRStatus(S * 2)
        self.specials += MultiReg(
            self.sample_out,
            self.data_peek.status
        )

        # CSRs for peeking at frame pattern
        self.data_peek = CSRStatus(S)
        self.specials += MultiReg(
            self.data_outs[2],
            self.data_peek.status
        )

        # CSR for moving a IDELAY2 up / down, doing a bitslip
        self.idelay_inc = CSR(1)
        self.idelay_dec = CSR(1)
        self.idelay_value = CSR(5)
        self.bitslip_csr = CSR(1)
        # Bitslip pulse needs to cross clock domains!
        self.submodules.bs_sync = PulseSynchronizer("sys", "sample")
        self.comb += [
            self.id_inc.eq(self.idelay_inc.re),
            self.id_dec.eq(self.idelay_dec.re),
            self.idelay_value.w.eq(self.id_value),
            self.bs_sync.i.eq(self.bitslip_csr.re),
            self.bitslip.eq(self.bs_sync.o)
        ]
