"""
Vector voltmeter
"""

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from migen.genlib.cdc import MultiReg
from os.path import join, dirname, abspath


class DspWrapper(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))

        srcs = [
            "dsp.v", "ddc.v", "cordicg_b22.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, src))

        srcs = [
            "rot_dds.v",
            "iq_mixer_multichannel.v", "mixer.v",
            "multi_sampler.v", "cic_multichannel.v",
            "serializer_multichannel.v", "reg_delay.v", "ccfilt.v",
            "double_inte_smp.v", "doublediff.v", "serialize.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, "../../../bedrock/dsp", src))

        srcs = [
            "cstageg.v", "addsubg.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, "../../../bedrock/cordic", src))


    def __init__(self, adc_chs=None):
        """
        adc_*:
            * 14 bit signed inputs
            * twos complement format
            * matched to LTC2175-14
        """
        self.strobe = Signal()
        if adc_chs is None:
            # Fake input for simulation
            adc_chs = [Signal((14, True)) for i in range(4)]
        self.adc_chs = adc_chs
        n_channels = len(adc_chs)

        self.mags = [Signal((20, False)) for i in range(n_channels)]
        self.phases = [Signal((21, True)) for i in range(n_channels)]

        self.ddc_ftw = CSRStorage(32, reset=0x40059350)
        self.ddc_deci = CSRStorage(13, reset=48)

        # CSRs for peeking at phase / magnitude values
        for i, val in enumerate(self.mags + self.phases):
            s_latch = Signal.like(val)
            self.sync.sample += If(self.strobe, s_latch.eq(val))
            if i <= 3:
                n = 'mag{:d}'.format(i)
            else:
                n = 'phase{:d}'.format(i - 4)
            csr = CSRStatus(20, name=n)
            setattr(self, n, csr)
            self.specials += MultiReg(s_latch, csr.status)

        self.specials += Instance("dsp",
            i_clk=ClockSignal("sample"),
            i_reset=ResetSignal("sample"),

            i_adc_ref=adc_chs[0],
            i_adc_a=adc_chs[1],
            i_adc_b=adc_chs[2],
            i_adc_c=0,

            o_mag_ref=self.mags[0],
            o_mag_a=self.mags[1],
            o_mag_b=self.mags[2],
            o_mag_c=self.mags[3],

            o_phase_ref=self.phases[0],
            o_phase_a=self.phases[1],
            o_phase_b=self.phases[2],
            o_phase_c=self.phases[3],

            o_out_strobe=self.strobe
        )
