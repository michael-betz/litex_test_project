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
        DDS.add_sources(platform)

    def __init__(self, adcs=None):
        """
        adc_*:
            * 14 bit signed inputs
            * twos complement format
            * matched to LTC2175-14
        """
        W_CORDIC = 31
        PHASE_BITS = W_CORDIC + 1
        MAG_BITS = W_CORDIC

        if adcs is None:
            # Mock input for simulation
            adcs = [Signal((14, True)) for i in range(4)]
        self.adcs = adcs
        n_ch = len(adcs)

        self.mags = [Signal((MAG_BITS, False)) for i in range(n_ch)]
        self.phases = [Signal((PHASE_BITS, True)) for i in range(n_ch)]
        self.cic_period = Signal(13)
        self.cic_shift = Signal(4)

        ###

        self.submodules.dds = ClockDomainsRenamer("sample")(DDS(18))

        result_strobe = Signal()
        # r2p_strobe = Signal()
        result_iq = Signal(W_CORDIC)
        result_iq_d = Signal.like(result_iq)
        self.sync.sample += result_iq_d.eq(result_iq)

        # Delay line for the strobe signal
        # self.specials += Instance(
        #     'reg_delay',
        #     p_dw=1,
        #     p_len=W_CORDIC + 2,

        #     i_clk=ClockSignal('sample'),
        #     i_reset=0,
        #     i_gate=1,
        #     i_din=result_strobe,

        #     o_dout=r2p_strobe
        # )

        # Digital down-conversion
        self.specials += Instance(
            'ddc',
            p_dw=14,
            p_oscw=18,
            p_davr=3,
            p_ow=W_CORDIC,
            p_rw=W_CORDIC,
            p_pcw=13,
            p_shift_base=7,
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
        mag_out = Signal(W_CORDIC)
        phase_out = Signal(W_CORDIC + 1)
        self.specials += Instance(
            'cordicg_b32',
            p_nstg=W_CORDIC,
            p_width=W_CORDIC,
            p_def_op=1,

            i_clk=ClockSignal('sample'),
            i_opin=Constant(1, 2),
            i_xin=result_iq_d,  # I
            i_yin=result_iq,    # Q
            i_phasein=Constant(0, W_CORDIC + 1),

            # o_yout=,
            o_xout=mag_out,
            o_phaseout=phase_out
        )
        CORDIC_DEL = W_CORDIC + 2

        # Latch the cordic output at the right time into the right place
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
        self.sync.sample += timeline(result_strobe, t)


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
