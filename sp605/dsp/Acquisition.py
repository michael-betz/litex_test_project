"""
For streaming ADC data to memory somehow

try
python3 Acquisition.py build
"""

from sys import argv
from migen import *


class Acquisition(Module):
    def __init__(self, depth=64):
        self.data_in = Signal(16)   # uint16

        ###

        self.specials.mem = Memory(16, depth)
        p1 = self.mem.get_port(write_capable=True)
        self.specials += p1
        self.comb += p1.dat_w.eq(self.data_in)
        self.sync += [
            p1.we.eq(0),
            If(p1.adr < depth - 1,
                p1.adr.eq(p1.adr + 1),
                p1.we.eq(1),
            )
        ]



def sample_generator(dut):
    for i in range(101):
        yield dut.data_in.eq(i)
        yield


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    dut = Acquisition()
    if "build" in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                dut.data_in
            },
            display_run=True
        ).write(argv[0].replace(".py", ".v"))
    if "sim" in argv:
        run_simulation(
            dut,
            sample_generator(dut),
            vcd_name=argv[0].replace(".py", ".vcd")
        )
