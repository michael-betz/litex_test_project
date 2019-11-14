"""
General purpose I2C master

arguments:
    build = generate a .v file for simulation with Icarus / general usage
    sim = run testbench in litex simulation and generate .vcd file

This file is Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
License: BSD
"""

import math
from sys import argv
from migen.fhdl.specials import Tristate
from migen.build.xilinx.common import xilinx_special_overrides
from migen import *
from litex.soc.interconnect.csr import *


# I2C Master ------------------------------------------------------------------
class I2CMaster(Module, AutoCSR):
    """2-wire I2C Master

    Provides a simple and minimal hardware I2C Master
    """
    pads_layout = [("scl", 1), ("sda", 1)]

    def __init__(self, sys_clk_freq, i2c_clk_freq=400e3):
        self.tx_word = Signal(9)  # LSB = ACK
        self.rx_word = Signal(9)  # LSB = ACK

        self.start = Signal()
        self.done = Signal()

        # 0 = IDLE, 1 = send byte, 2 = send start, 3 = send stop
        self.mode = Signal(2)

        self.scl = Signal(reset=1)
        self.sda = Signal(reset=1)
        self.sda_i = Signal()

        # # #

        self.tx_word_ = Signal.like(self.tx_word)


        # Clock generation ----------------------------------------------------
        clk_divide = math.ceil(sys_clk_freq / i2c_clk_freq)
        self.clk_divider = Signal(max=clk_divide)
        self.clk_rise = Signal()
        self.clk_fall = Signal()
        self.sync += [
            If(self.clk_fall,
                self.clk_divider.eq(0)
            ).Else(
                self.clk_divider.eq(self.clk_divider + 1)
            )
        ]
        self.comb += [
            self.clk_rise.eq(self.clk_divider == (clk_divide // 2 - 1)),
            self.clk_fall.eq(self.clk_divider == (clk_divide - 1))
        ]

        # Control FSM ---------------------------------------------------------
        self.bits = Signal(4)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.start & (self.mode != 0),
                NextState("SYNC")
            ),
            self.done.eq(1),
        )
        fsm.act("SYNC",
            If(self.clk_rise,
                If(self.mode == 1,
                    NextState("XFER"),
                    NextValue(self.tx_word_, self.tx_word)
                ),
                If(self.mode == 2,
                    NextValue(self.sda, 1),
                    NextValue(self.scl, 1),
                    NextState("START")
                ),
                If(self.mode == 3,
                    NextValue(self.sda, 0),
                    NextValue(self.scl, 1),
                    NextState("STOP")
                ),
            )
        )
        fsm.act("START",
            If(self.clk_fall,
                NextValue(self.sda, 0),
                NextState("IDLE")
            )
        )
        fsm.act("STOP",
            If(self.clk_fall,
                NextValue(self.sda, 1),
                NextState("IDLE")
            )
        )
        fsm.act("XFER",
            If(self.clk_fall,
                NextValue(self.tx_word_, Cat(0, self.tx_word_[:-1])),
                NextValue(self.sda, self.tx_word_[-1]),
                NextValue(self.scl, 0),
            ),
            If(self.clk_rise,
                NextValue(self.bits, self.bits + 1),
                NextValue(self.scl, 1),
                If(self.bits == 9,
                    NextState("IDLE"),
                    NextValue(self.bits, 0),
                    NextValue(self.scl, 0),
                    NextValue(self.sda, 1)
                ).Else(
                    NextValue(self.rx_word, Cat(
                        self.sda_i,
                        self.rx_word[:-1]
                    ))
                )
            )
        )

    def add_pads(self, pads):
        sda_oe = Signal()
        self.comb += [
            sda_oe.eq(~self.sda),
            pads.scl.eq(self.scl)
        ]
        self.specials += Tristate(pads.sda, self.sda, sda_oe, self.sda_i)

    def add_csr(self):
        self._control = CSRStorage(fields=[
            CSRField("start", size=1, offset=0, pulse=True),
            CSRField("mode", size=2, offset=4, values=[
                (0, "Do nothing"),
                (1, "RX_ / TX_WORD"),
                (2, "Send START"),
                (3, "Send STOP")
            ]),
            CSRField("tx_byte", size=8, offset=8),
            CSRField("tx_ack", size=1, offset=16)
        ])

        self._status = CSRStatus(fields=[
            CSRField("done", size=1, offset=0),
            CSRField("rx_byte", size=8, offset=8),
            CSRField("rx_ack", size=1, offset=16)
        ])

        self.sync += [
            self.start.eq(self._control.fields.start),
            self.mode.eq(self._control.fields.mode),
            self.tx_word.eq(Cat(
                self._control.fields.tx_ack,
                self._control.fields.tx_byte
            )),
            self._status.fields.done.eq(self.done),
            self._status.fields.rx_byte.eq(self.rx_word[1:]),
            self._status.fields.rx_ack.eq(self.rx_word[0])
        ]


def tb_send(i):
    yield dut.mode.eq(i)
    yield dut.start.eq(1)
    yield
    yield dut.start.eq(0)
    yield
    while (yield dut.done) == 0:
        yield


def i2c_tb(dut):
    for i in range(10):
        yield
    yield from tb_send(2)  # Send START
    yield dut.tx_word.eq((0x83 << 1) | 0)
    yield from tb_send(1)  # Send TX_WORD
    yield from tb_send(2)  # Send REP_START
    yield dut.tx_word.eq((0x83 << 1) | 1)
    yield from tb_send(1)  # Send TX_WORD
    yield dut.tx_word.eq((0x83 << 1) | 1)
    yield from tb_send(1)  # Send TX_WORD
    yield from tb_send(3)  # Send STOP
    for i in range(10):
        yield


if __name__ == "__main__":
    if len(argv) == 1:
        print(__doc__)
        exit(0)
    tName = argv[0].replace('.py', '')
    dut = I2CMaster(0.4e6 * 128)
    if "build" in argv:
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={
                dut.start,
                dut.done,
                dut.mode,
                dut.rx_word,
                dut.tx_word
            },
            name=tName,
            display_run=True
        ).write(tName + '.v')
    if "sim" in argv:
        tb = i2c_tb(dut)
        run_simulation(
            dut,
            tb,
            special_overrides=xilinx_special_overrides,
            vcd_name=tName + '.vcd'
        )
