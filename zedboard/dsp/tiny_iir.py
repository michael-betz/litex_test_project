'''
Tiny first order IIR filter without multipliers
  * there's a DC error when shifts > ACC_W - IO_W
https://zipcpu.com/dsp/2017/08/19/simple-filter.html
'''
from migen import *
from migen.fhdl import verilog
from matplotlib.pyplot import *
from numpy import *
from sys import argv


class TinyIIR(Module):
    def __init__(self, IO_W=8, ACC_W=16):
        self.strobe = Signal()
        self.x = Signal((IO_W, True))
        self.y = Signal.like(self.x)
        self.shifts = Signal(5)

        ###

        acc = Signal((ACC_W, True))
        acc_ = Signal.like(acc)
        x_hr = Signal.like(acc)
        delta = Signal.like(acc)
        strobe_ = Signal()

        self.comb += [
            x_hr.eq(self.x << (ACC_W - IO_W)),
            self.y.eq(acc >> (ACC_W - IO_W)),
        ]
        self.sync += [
            strobe_.eq(self.strobe),
            If(self.strobe,
                delta.eq(x_hr - acc_)
            ),
            If(strobe_,
                acc.eq(acc_ + (delta >> self.shifts)),
                acc_.eq(acc),
            )
        ]


def fir_tb(dut):
    maxValue = (1 << (len(dut.x) - 1))
    yield dut.x.eq(maxValue - 1)
    yield dut.shifts.eq(4)
    for i in range(10000):
        if i == 5000:
            yield dut.x.eq(-maxValue)
        yield dut.strobe.eq(1)
        yield
        yield dut.strobe.eq(0)
        yield
        yield


if __name__ == "__main__":
    tName = argv[0].replace('.py', '')
    dut = TinyIIR(8, 8 + 5)
    tb = fir_tb(dut)
    run_simulation(dut, tb, vcd_name=tName + '.vcd')
