from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.cores import gpio

from pwm import PWM

# see:
# https://github.com/enjoy-digital/litex/blob/master/litex/soc/cores/gpio.py

class Led(gpio.GPIOOut):
    pass

class RGBLed(Module, AutoCSR):
    def __init__(self, pads):
        _r = Signal()
        _g = Signal()
        _b = Signal()
        self.submodules.r = PWM(_r)
        self.submodules.g = PWM(_g)
        self.submodules.b = PWM(_b)
        self.comb += [
            pads.r.eq(~_r),
            pads.g.eq(~_g),
            pads.b.eq(~_b)
        ]

class Button(gpio.GPIOIn):
    pass

class Switch(gpio.GPIOIn):
    pass
