'''
For understanding the cordic.py module

try
python3 cordic_test.py build
'''
from sys import argv
from migen import *
from litex.soc.cores.cordic import Cordic


class CordicTest(Module):
    def __init__(self):
        self.submodules.cordic = Cordic(
            width=8,
            eval_mode='pipelined',
            cordic_mode='rotate',
            func_mode='circular'
        )


def sys_generator(dut):
    yield (dut.cordic.xi.eq(120))
    yield
    for i in range(100):
        yield (dut.cordic.zi.eq(i))
        yield


def main():
    tName = argv[0].replace('.py', '')
    dut = CordicTest()
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                dut.cordic.zi,
                dut.cordic.xo,
                dut.cordic.yo,
                dut.cordic.zo
            },
            display_run=True
        ).write(tName + '.v')
    if 'sim' in argv:
        run_simulation(
            dut,
            sys_generator(dut),
            vcd_name=tName + '.vcd'
        )


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
