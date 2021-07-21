'''
'''
from migen import *
from sim_soc import SimSoC, main
from litex.soc.interconnect import wishbone


class SimMem(SimSoC):
    '''
    try to re-produce a wishbone access problem with
    SRAM bigger than 1024 words in simulation
    '''

    def __init__(self):
        SimSoC.__init__(self, cpu_type=None)
        # ----------------------------
        #  memory to test
        # ----------------------------
        mem = Memory(32, 4096 // 2, init=[1, 0xDEAD, 0xBEEF, 0xC0FE, 0xAFFE])
        self.specials += mem
        self.submodules.sample_ram = wishbone.SRAM(mem)
        self.register_mem(
            "sram",
            0x10000000,  # [bytes]
            self.sample_ram.bus,
            mem.depth * 4  # [bytes]
        )
        # p2 = mem.get_port(write_capable=True, clock_domain="sys")
        # self.specials += p2
        # self.sync += [
        #     p2.we.eq(1),
        #     p2.adr.eq(p2.adr + 1),
        #     p2.dat_w.eq(p2.adr + 1)
        # ]


if __name__ == "__main__":
    main(SimMem())
