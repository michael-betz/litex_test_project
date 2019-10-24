"""
Digital signal processing to implement a Vector voltmeter.

try:
    python3 vvm_dsp.py build
"""

from sys import argv
from migen import *
from migen.genlib.misc import timeline
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus
from migen.genlib.cdc import BlindTransfer
from os.path import join, dirname, abspath
from dds import DDS


class VVM_DSP(Module, AutoCSR):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))
        DDS.add_sources(platform)

        srcs = [
            "ddc.v", "cordicg_b32.v"
        ]
        for src in srcs:
            platform.add_source(join(vdir, src))

        srcs = [
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

    def __init__(self, adcs=None):
        """
        adc_*:
            * 14 bit signed inputs
            * twos complement format
            * matched to LTC2175-14
        """
        self.W_CORDIC = 30
        self.PHASE_BITS = self.W_CORDIC + 1
        self.MAG_BITS = self.W_CORDIC

        if adcs is None:
            # Mock input for simulation
            adcs = [Signal((14, True)) for i in range(4)]
        self.adcs = adcs
        n_ch = len(adcs)

        self.mags = [Signal((self.MAG_BITS, False)) for i in range(n_ch)]
        self.phases = [Signal((self.PHASE_BITS, True)) for i in range(n_ch)]
        self.cic_period = Signal(13)
        self.cic_shift = Signal(4)

        ###

        self.submodules.dds = ClockDomainsRenamer("sample")(DDS(18))

        result_strobe = Signal()
        # r2p_strobe = Signal()
        result_iq = Signal(self.W_CORDIC)
        result_iq_d = Signal.like(result_iq)
        self.sync.sample += result_iq_d.eq(result_iq)

        # Digital down-conversion
        self.specials += Instance(
            'ddc',
            p_dw=14,  # ADC input width
            p_oscw=18,  # LO width
            p_davr=2,  # Mixer guard bits
            # CIC integrator width (aka. di_rwi)
            # Increase this to achieve higher decimation factors
            p_ow=self.W_CORDIC + 13,  # XXX optimize bit-widths!
            p_rw=self.W_CORDIC,  # CIC output width (aka. cc_outw)
            p_pcw=13,  # decimation factor width
            p_shift_base=7,  # Bits to discard in CIC
            p_nadc=4,

            i_clk=ClockSignal('sample'),
            i_reset=ResetSignal('sample'),
            i_adcs=Cat(self.adcs),
            i_cosa=self.dds.o_cos,
            i_sina=self.dds.o_sin,
            i_cic_period=self.cic_period,
            i_cic_shift=self.cic_shift,

            o_result_iq=result_iq,
            o_strobe_cc=result_strobe
        )

        # Rectangular to Polar conversion
        mag_out = Signal(self.W_CORDIC)
        phase_out = Signal(self.W_CORDIC + 1)
        self.specials += Instance(
            'cordicg_b32',
            p_nstg=self.W_CORDIC,
            p_width=self.W_CORDIC,
            p_def_op=1,

            i_clk=ClockSignal('sample'),
            i_opin=Constant(1, 2),
            i_xin=result_iq_d,  # I
            i_yin=result_iq,    # Q
            i_phasein=Constant(0, self.W_CORDIC + 1),

            # o_yout=,
            o_xout=mag_out,
            o_phaseout=phase_out
        )
        CORDIC_DEL = self.W_CORDIC + 2

        # Latch the cordic output at the right time into the right place
        self.strobe = Signal()
        t = []
        for i in range(n_ch):
            instrs = [self.mags[i].eq(mag_out)]
            if i == 0:
                instrs += [self.phases[i].eq(phase_out)]
            else:
                instrs += [self.phases[i].eq(self.phases[0] - phase_out)]
            t += [(
                CORDIC_DEL + 2 * i,  # N cycles after result_strobe ...
                instrs               # ... carry out these instructions
            )]
        t[-1][1].append(self.strobe.eq(1))
        self.sync.sample += self.strobe.eq(0)
        self.sync.sample += timeline(result_strobe, t)

    def add_csrs(self):

        # sys clock domain
        n_ch = len(self.adcs)
        self.mags_sys = [Signal((self.MAG_BITS, False)) for i in range(n_ch)]
        self.phases_sys = [Signal((self.PHASE_BITS, True)) for i in range(n_ch)]

        # Clock domain crossing
        self.submodules.cdc = BlindTransfer(
            "sample",
            "sys",
            n_ch * (self.MAG_BITS + self.PHASE_BITS)
        )

        self.ddc_ftw = CSRStorage(32, reset=0x40059350)
        self.ddc_deci = CSRStorage(13, reset=48)

        self.comb += [
            self.dds.ftw.eq(self.ddc_ftw.storage),
            self.cic_period.eq(self.ddc_deci.storage),
            self.cdc.data_i.eq(Cat(self.mags + self.phases)),
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


def main():
    tName = argv[0].replace('.py', '')
    d = VVM_DSP()
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            d,
            name=tName,
            ios={
                *d.adcs,
                *d.mags,
                *d.phases,
                d.cic_period,
                d.cic_shift,
                d.dds.ftw
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
