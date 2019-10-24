'''
Simple DDS
try:
    python3 dds.py build
'''
from sys import argv
from migen import *


class DDS(Module):
    @staticmethod
    def add_sources(platform):
        vdir = abspath(dirname(__file__))
        platform.add_source(join(vdir, "cordicg_b32.v"))

    def __init__(self, N_BITS=24):
        '''
        DDS with 32 bit accumulator
        and `N` output bits (max = 32)
        Use ClockDomainRenamer to specify the DDS clock
        '''
        # sin, cos outputs
        self.o_sin = Signal((N_BITS, True))
        self.o_cos = Signal((N_BITS, True))

        # Frequency tuning word, f_out = f_clk * ftw / 2**32
        self.ftw = Signal(32, reset=1)

        # Output amplitude
        self.amp = Signal(N_BITS, reset=int((1 << N_BITS) / 1.7))

        ###

        self.phase = Signal(32)
        self.sync += [
            self.phase.eq(self.phase + self.ftw)
        ]

        self.specials += Instance(
            "cordicg_b32",
            p_nstg=N_BITS,
            p_width=N_BITS,
            p_def_op=0,

            i_clk=ClockSignal(),
            i_opin=Constant(0, 2),
            i_xin=self.amp,
            i_yin=Constant(0, N_BITS),
            i_phasein=self.phase[-N_BITS - 1:],

            o_xout=self.o_cos,
            o_yout=self.o_sin
        )


def main():
    tName = argv[0].replace('.py', '')
    d = DDS()
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            d,
            ios={
                d.o_sin,
                d.o_cos,
                d.ftw,
                d.amp
            },
            display_run=True
        ).write(tName + '.v')


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
