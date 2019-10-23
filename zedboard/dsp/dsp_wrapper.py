"""
Vector voltmeter
"""

from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from migen.genlib.cdc import BlindTransfer
from os.path import join, dirname, abspath


class DspWrapper(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))

        srcs = [
            "dsp.v", "ddc.v", "cordicg_b22.v", "cordicg_b32.v"
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
        W_CORDIC = 31
        PHASE_BITS = W_CORDIC + 1
        MAG_BITS = W_CORDIC

        self.strobe = Signal()
        if adc_chs is None:
            # Fake input for simulation
            adc_chs = [Signal((14, True)) for i in range(4)]
        self.adc_chs = adc_chs
        n_ch = len(adc_chs)

        self.ddc_ftw = CSRStorage(32, reset=0x40059350)
        self.ddc_deci = CSRStorage(13, reset=48)

        # sample clock domain
        self.mags_dsp = [Signal((MAG_BITS, False)) for i in range(n_ch)]
        self.phases_dsp = [Signal((PHASE_BITS, True)) for i in range(n_ch)]

        # sys clock domain
        self.mags_sys = [Signal((MAG_BITS, False)) for i in range(n_ch)]
        self.phases_sys = [Signal((PHASE_BITS, True)) for i in range(n_ch)]

        # Clock domain crossing
        self.submodules.cdc = BlindTransfer(
            "sample",
            "sys",
            n_ch * (MAG_BITS + PHASE_BITS)
        )

        self.comb += [
            self.cdc.data_i.eq(Cat(self.mags_dsp + self.phases_dsp)),
            self.cdc.i.eq(self.strobe),
            Cat(self.mags_sys + self.phases_sys).eq(self.cdc.data_o)
        ]

        # CSRs for peeking at phase / magnitude values
        for i, sig in enumerate(self.mags_sys + self.phases_sys):
            if i <= 3:
                n = 'mag{:d}'.format(i)
            else:
                n = 'phase{:d}'.format(i - 4)
            csr = CSRStatus(32, name=n)
            setattr(self, n, csr)
            self.comb += csr.status.eq(sig)

        self.specials += Instance("dsp",
            p_W_CORDIC=W_CORDIC,

            i_clk=ClockSignal("sample"),
            i_reset=ResetSignal("sample"),

            i_adc_ref=adc_chs[0],
            i_adc_a=adc_chs[1],
            i_adc_b=adc_chs[2],
            i_adc_c=adc_chs[3],

            i_dds_ftw=self.ddc_ftw.storage,
            i_decimation=self.ddc_deci.storage,

            # i_debug_i=csr_debug_i.

            o_mag_ref=self.mags_dsp[0],
            o_mag_a=self.mags_dsp[1],
            o_mag_b=self.mags_dsp[2],
            o_mag_c=self.mags_dsp[3],

            o_phase_ref=self.phases_dsp[0],
            o_phase_a=self.phases_dsp[1],
            o_phase_b=self.phases_dsp[2],
            o_phase_c=self.phases_dsp[3],

            o_out_strobe=self.strobe
        )
