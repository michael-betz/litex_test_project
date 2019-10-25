'''
Tiny IIR filter
https://zipcpu.com/dsp/2017/08/19/simple-filter.html
'''
from migen import *


class TinyIIR(Module):

    def __init__(self, N_BITS=24):
        self.strobe = Signal()
        self.x = Signal((N_BITS, True))
        self.y = Signal.like(self.x)
        self.shifts = Signal(6)

        ###

        y_ = Signal.like(self.x)
        self.sync += [
            If(self.strobe,
                self.y.eq(y_ + ((self.x - y_) >> self.shifts)),
                y_.eq(self.y)
            )
        ]
