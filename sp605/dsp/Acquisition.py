"""
For streaming ADC data to memory somehow

try
python3 Acquisition.py build
"""

from sys import argv
from migen import *
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage
from migen.genlib.cdc import PulseSynchronizer


class Acquisition(Module, AutoCSR):
    def __init__(self, mem=None):
        """
        acquisition starts after
          * rising edge on self.trigger
          * data_in crossing trig_level
        """
        self.data_in = Signal(16)   # uint16
        self.trigger = Signal()
        self.busy = Signal()
        self.clock_domains.sample = ClockDomain()

        ###

        trig = Signal()
        self.trig_csr = CSR()
        self.trig_level = CSRStorage(16, reset=(1 << 15))

        if mem is None:
            mem = Memory(16, 12)
        self.specials += mem
        p1 = mem.get_port(write_capable=True, clock_domain="sample")
        self.specials += p1
        self.comb += p1.dat_w.eq(self.data_in)
        self.submodules.fsm = ClockDomainsRenamer("sample")(FSM())
        trig_d = Signal()
        data_in_d = Signal.like(self.data_in)
        self.sync.sample += [
            trig_d.eq(trig),
            data_in_d.eq(self.data_in)
        ]
        self.fsm.act("WAIT_TRIGGER",
            If(trig & ~trig_d,
                NextState("WAIT_LEVEL")
            )
        )
        self.fsm.act("WAIT_LEVEL",
            If((data_in_d < self.trig_level.storage) &
               (self.data_in >= self.trig_level.storage),
                p1.we.eq(1),
                NextValue(p1.adr, p1.adr + 1),
                NextState("ACQUIRE")
            )
        )
        self.fsm.act("ACQUIRE",
            p1.we.eq(1),
            NextValue(p1.adr, p1.adr + 1),
            If(p1.adr >= mem.depth - 1,
                NextState("WAIT_TRIGGER"),
                NextValue(p1.adr, 0)
            )
        )
        self.submodules.trig_sync = PulseSynchronizer("sys", "sample")
        self.comb += [
            self.busy.eq(p1.we),
            self.trig_sync.i.eq(self.trig_csr.re),
            trig.eq(self.trigger | self.trig_sync.o)
        ]


def sample_generator(dut):
    yield dut.trig_level.storage.eq(30)
    for i in range(101):
        yield dut.trigger.eq(0)
        yield dut.data_in.eq(i)
        if i == 15 or i == 75:
            yield dut.trigger.eq(1)
        yield


def main():
    dut = Acquisition()
    if "build" in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                dut.sample.clk,
                dut.data_in,
                dut.trigger
            },
            display_run=True
        ).write(argv[0].replace(".py", ".v"))
    if "sim" in argv:
        run_simulation(
            dut,
            {"sample": sample_generator(dut)},
            {"sys": 10, "sample": 9},
            vcd_name=argv[0].replace(".py", ".vcd")
        )


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
