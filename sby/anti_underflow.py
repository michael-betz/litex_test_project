#
# This file is part of LiteEth.
#
# SPDX-License-Identifier: BSD-2-Clause

from sys import argv
from liteeth.common import *
from litex.soc.interconnect.packet import PacketFIFO
from litex.gen.fhdl.verilog import convert


class LiteEthAntiUnderflow(Module):
    def __init__(self, stream_description, depth=32):
        '''
        buffers a whole packet and releases it at once
        workaround for driving PHYs with wide datapaths which expect a
        continuous stream
        '''
        self.sink   = sink   = stream.Endpoint(stream_description)
        self.source = source = stream.Endpoint(stream_description)

        # # #

        self.submodules.fifo = fifo = PacketFIFO(
            layout=stream_description,
            payload_depth=depth,
            param_depth=1,
            buffered=True
        )

        self.comb += [
            sink.connect(fifo.sink),
            fifo.source.connect(source, omit=['valid', 'ready'])
        ]

        self.submodules.fsm = fsm = FSM(reset_state="STORE")
        fsm.act("STORE",
            If(sink.valid & sink.last | (fifo.payload_fifo.level >= fifo.payload_fifo.depth - 1),
                NextState("FLUSH")
            )
        )
        fsm.act("FLUSH",
            fifo.source.connect(source, keep=['valid', 'ready']),
            If(fifo.source.valid & fifo.source.last & source.ready,
                NextState("STORE")
            )
        )


def main():
    tName = argv[0].replace('.py', '')
    # ------------------------------------------
    #  Generate Verilog
    # ------------------------------------------
    dut = LiteEthAntiUnderflow(eth_phy_description(32), 4)
    dut.clock_domains.sys = ClockDomain('sys')
    convert(
        dut,
        ios={
            # Clock and synchronous reset signal
            dut.sys.clk,
            dut.sys.rst,
            # data stream
            *dut.sink.flatten(),
            *dut.source.flatten()
        },
        name=tName
    ).write(tName + '.v')
    print('wrote', tName + '.v')


if __name__ == "__main__":
    main()
