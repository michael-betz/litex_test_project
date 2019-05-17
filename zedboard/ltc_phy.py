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
    def __init__(self, platform, f_enc):
        N_CHANNELS = 4
        S = 8
        D = N_CHANNELS * 2 + 1

        self.sample_outs = [Signal(S * 2)] * N_CHANNELS

        ###

        # Note: LTC2175 streams the MSB first and needs bit-mirroring
        S7_iserdes.__init__(
            self,
            S=S,
            D=D,
            # OUT0_A / _B and OUT1_A / _B are in a different clock region!
            clock_regions=[0, 0, 0, 0, 1, 1, 1, 1, 1]
        )

        pads_dco = platform.request("LTC_DCO")
        self.comb += [
            self.dco_p.eq(pads_dco.p),
            self.dco_n.eq(pads_dco.n)
        ]

        dat_p = []
        dat_n = []
        for i in range(N_CHANNELS):  # For each ADC channel
            pads_out = platform.request("LTC_OUT", i)
            # Wire up the input pads to the serial serdes inputs
            dat_p.append(pads_out.a_p)
            dat_p.append(pads_out.b_p)
            dat_n.append(pads_out.a_n)
            dat_n.append(pads_out.b_n)
            # re-arrange parallel serdes outputs to form samples
            sample_out = self.sample_outs[i]
            self.comb += sample_out.eq(
                Cat(myzip(self.data_outs[2 * i + 1], self.data_outs[2 * i]))
            )
            # CSRs for peeking at data patterns
            # LVDS_B (data_outs[1]) has the LSB and needs to come first!
            n = 'data_peek{:d}'.format(i)
            data_peek = CSRStatus(S * 2, name=n)
            setattr(self, n, data_peek)
            self.specials += MultiReg(
                sample_out,
                data_peek.status
            )

        # Add frame signal to serial inputs
        pads_frm = platform.request("LTC_FR")
        dat_p.append(pads_frm.p)
        dat_n.append(pads_frm.n)
        self.comb += [
            self.lvds_data_p.eq(Cat(dat_p)),
            self.lvds_data_n.eq(Cat(dat_n))
        ]

        # CSRs for peeking at parallelized frame pattern
        self.frame_peek = CSRStatus(S)
        self.specials += MultiReg(
            self.data_outs[-1],
            self.frame_peek.status
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
