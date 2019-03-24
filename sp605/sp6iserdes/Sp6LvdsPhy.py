from migen import *
from litex.soc.interconnect.csr import *
import os


class Sp6LvdsPhy(Module):
    def __init__(self, S=8, D=2):
        self.dco_p = Signal()
        self.dco_n = Signal()
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)
        self.data_out = Signal(S * D)
        self.clk_out = Signal()

        ###

        rxioclkp = Signal()
        rxioclkn = Signal()
        serdesstrobe = Signal()

        self.specials += Instance(
            "serdes_1_to_n_clk_ddr_s8_diff",
            p_S=S,
            i_clkin_p=self.dco_p,
            i_clkin_n=self.dco_n,
            o_rxioclkp=rxioclkp,
            o_rxioclkn=rxioclkn,
            o_rx_serdesstrobe=serdesstrobe,
            o_rx_bufg_x1=self.clk_out
        )

        self.specials += Instance(
            "serdes_1_to_n_data_ddr_s8_diff",
            p_S=S,
            p_D=D,
            i_use_phase_detector=1,
            i_datain_p=self.lvds_data_p,
            i_datain_n=self.lvds_data_n,
            i_rxioclkp=rxioclkp,
            i_rxioclkn=rxioclkn,
            i_rxserdesstrobe=serdesstrobe,
            i_reset=ResetSignal(),
            i_gclk=ClockSignal(),
            i_bitslip=0,
            o_data_out=self.data_out
        )

    @staticmethod
    def add_sources(platform):
        vdir = os.path.abspath(os.path.dirname(__file__))
        platform.add_source(
            os.path.join(vdir, "serdes_1_to_n_clk_ddr_s8_diff.v")
        )
        platform.add_source(
            os.path.join(vdir, "serdes_1_to_n_data_ddr_s8_diff.v")
        )


class LTCPhy(Sp6LvdsPhy, AutoCSR):
    def __init__(self, platform):
        Sp6LvdsPhy.__init__(self, S=8, D=2)
        pads_dco = platform.request("LTC_DCO")
        pads_ch0 = platform.request("LTC_OUT", 0)
        self.data_peek = CSRStatus(16)
        self.comb += [
            self.dco_p.eq(pads_dco.p),
            self.dco_n.eq(pads_dco.n),
            self.lvds_data_p.eq(Cat(pads_ch0.a_p, pads_ch0.b_p)),
            self.lvds_data_n.eq(Cat(pads_ch0.a_n, pads_ch0.b_n)),
            self.data_peek.status.eq(self.data_out)
        ]
        Sp6LvdsPhy.add_sources(platform)
