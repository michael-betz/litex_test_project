from migen import *
import os


class Sp6LvdsPhy(Module):
    def __init__(self, S=8, D=2, DCO_CLK_PERIOD_NS=2.0):
        self.dco_p = Signal()
        self.dco_n = Signal()
        self.lvds_data_p = Signal(D)
        self.lvds_data_n = Signal(D)
        self.data_out = Signal(S * D)
        self.clk_out = Signal()
        self.bitslip = Signal()    # Pulse to rotate the ISERDES output bits

        ###

        rxioclk = Signal()
        serdesstrobe = Signal()

        self.specials += Instance(
            "serdes_1_to_n_clk_pll_s8_diff",
            p_S=S,
            p_PLLX=2,
            p_CLKIN_PERIOD=DCO_CLK_PERIOD_NS,
            p_BS="FALSE",
            i_clkin_p=self.dco_p,
            i_clkin_n=self.dco_n,
            i_reset=ResetSignal(),
            o_rxioclk=rxioclk,
            o_rx_serdesstrobe=serdesstrobe,
            o_rx_bufg_pll_x1=self.clk_out
        )

        self.specials += Instance(
            "serdes_1_to_n_data_s8_diff",
            p_S=S,
            p_D=D,
            i_use_phase_detector=1,
            i_datain_p=self.lvds_data_p,
            i_datain_n=self.lvds_data_n,
            i_rxioclk=rxioclk,
            i_rxserdesstrobe=serdesstrobe,
            i_reset=ResetSignal(),
            i_gclk=ClockSignal(),
            i_bitslip=self.bitslip,
            o_data_out=self.data_out
        )

    @staticmethod
    def add_sources(platform):
        vdir = os.path.abspath(os.path.dirname(__file__))
        platform.add_source(
            os.path.join(vdir, "serdes_1_to_n_clk_pll_s8_diff.v")
        )
        platform.add_source(
            os.path.join(vdir, "serdes_1_to_n_data_s8_diff.v")
        )
