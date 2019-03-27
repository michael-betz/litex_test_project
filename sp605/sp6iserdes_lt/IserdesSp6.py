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


class IserdesSp6(Module):
    def __init__(self, S=8, D=2):
        self.lvds_data_p = Signal(D)   # data lanes
        self.lvds_data_n = Signal(D)
        # parallel data out, S-bit serdes on D-lanes
        self.data_outs = [Signal(S) for i in range(D)]
        self.clk_out = Signal()        # dat aout clock
        self.bitslip = Signal()        # Pulse to rotate
        self.serdesstrobe = Signal()

        self.clock_domains.dco2x = ClockDomain()   # LVDS bit clock
        self.clock_domains.sample = ClockDomain()  # ADC sample clock

        ###

        idelay_default = {
            "p_SIM_TAPDELAY_VALUE": 49,
            "p_DATA_RATE": "SDR",
            "p_IDELAY_VALUE": 0,
            "p_IDELAY2_VALUE": 0,
            "p_ODELAY_VALUE": 0,
            "p_IDELAY_MODE": "NORMAL",
            "p_IDELAY_TYPE": "DIFF_PHASE_DETECTOR",
            "p_COUNTER_WRAPAROUND": "WRAPAROUND",
            "p_DELAY_SRC": "IDATAIN",
            "i_T": 1,
            "i_ODATAIN": 0,
            "i_IOCLK0": ClockSignal("dco2x"),
            "i_IOCLK1": 0,
            "i_CLK": ClockSignal("sample"),
             # A faire: wire these up
            "i_CAL": 0,
            "i_INC": 0,
            "i_CE": 0,
            "i_RST": 0,
            # "o_BUSY":
        }

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
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_m,
                **idelay_default
            )
            self.specials += Instance(
                "IODELAY2",
                p_SERDES_MODE="SLAVE",
                i_IDATAIN=lvds_data,
                o_DATAOUT=lvds_data_s,
                **idelay_default
            )
            iserdes_default = {
                "p_DATA_WIDTH": S,
                "p_DATA_RATE": "SDR",
                "p_BITSLIP_ENABLE": "TRUE",
                "p_INTERFACE_TYPE": "RETIMED",
                "i_CE0": 1,
                "i_CLK0": ClockSignal("dco2x"),
                "i_CLK1": 0,
                "i_IOCE": self.serdesstrobe,
                "i_RST": ResetSignal("sample"),
                "i_CLKDIV": ClockSignal("sample"),
                "i_BITSLIP": self.bitslip
            }
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


# class S6Clocking(Module, AutoCSR):
#     def __init__(self, pads, clkin_freq=None, M=2, S=8):
#         self._pll_reset = CSRStorage(reset=1)
#         self._locked = CSRStatus()

#         self.locked = Signal()
#         self.serdesstrobe = Signal()
#         self.clock_domains._cd_pix = ClockDomain()
#         self.clock_domains._cd_pix_o = ClockDomain()
#         self.clock_domains._cd_pix2x = ClockDomain()
#         self.clock_domains._cd_pix10x = ClockDomain(reset_less=True)

#         # # #

#         self.clk_input = Signal()
#         self.specials += Instance("IBUFDS", name="hdmi_in_ibufds",
#                                   i_I=pads.clk_p, i_IB=pads.clk_n,
#                                   o_O=self.clk_input)

#         clkfbout = Signal()
#         pll_locked = Signal()
#         pll_clk0 = Signal()
#         pll_clk1 = Signal()
#         pll_clk2 = Signal()
#         pll_drdy = Signal()
#         self.sync += If(self._pll_read.re | self._pll_write.re,
#             self._pll_drdy.status.eq(0)
#         ).Elif(pll_drdy,
#             self._pll_drdy.status.eq(1)
#         )
#         self.specials += [
#             Instance("PLL_ADV",
#                 p_CLKFBOUT_MULT=M,
#                 p_CLKOUT0_DIVIDE=1,
#                 p_CLKOUT1_DIVIDE=1,
#                 p_CLKOUT2_DIVIDE=S,
#                 p_COMPENSATION="SOURCE_SYNCHRONOUS",
#                 p_CLK_FEEDBACK="CLKOUT0",

#                 i_CLKINSEL=1,
#                 i_CLKIN1=self.clk_input,
#                 o_CLKOUT0=pll_clk0, o_CLKOUT1=pll_clk1, o_CLKOUT2=pll_clk2,
#                 o_CLKFBOUT=clkfbout, i_CLKFBIN=clkfbout,
#                 o_LOCKED=pll_locked, i_RST=self._pll_reset.storage,

#                 i_DADDR=self._pll_adr.storage,
#                 o_DO=self._pll_dat_r.status,
#                 i_DI=self._pll_dat_w.storage,
#                 i_DEN=self._pll_read.re | self._pll_write.re,
#                 i_DWE=self._pll_write.re,
#                 o_DRDY=pll_drdy,
#                 i_DCLK=ClockSignal())
#         ]

#         locked_async = Signal()
#         self.specials += [
#             Instance("BUFPLL", name="hdmi_in_bufpll", p_DIVIDE=5,
#                 i_PLLIN=pll_clk0, i_GCLK=ClockSignal("pix2x"), i_LOCKED=pll_locked,
#                 o_IOCLK=self._cd_pix10x.clk, o_LOCK=locked_async, o_SERDESSTROBE=self.serdesstrobe),
#             Instance("BUFG", name="hdmi_in_pix2x_bufg", i_I=pll_clk1, o_O=self._cd_pix2x.clk),
#             Instance("BUFG", name="hdmi_in_pix_bufg", i_I=pll_clk2, o_O=self._cd_pix.clk),
#             MultiReg(locked_async, self.locked, "sys")
#         ]
#         self.comb += self._locked.status.eq(self.locked)

#         self.specials += [
#             AsyncResetSynchronizer(self._cd_pix, ~locked_async),
#             AsyncResetSynchronizer(self._cd_pix2x, ~locked_async),
#         ]
#         self.comb += self._cd_pix_o.clk.eq(self._cd_pix.clk)

if __name__ == '__main__':
    from migen.fhdl.verilog import convert
    d = IserdesSp6()
    convert(
        d,
        ios={
            d.dco2x.clk,
            d.sample.clk,
            d.serdesstrobe,
            d.bitslip,
            d.lvds_data_p,
            d.lvds_data_n,
            *d.data_outs
            # d.clk_out
        },
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
