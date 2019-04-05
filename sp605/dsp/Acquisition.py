"""
For streaming ADC data to memory somehow
"""

from sys import argv, path
from migen import *
from litex.soc.interconnect.csr import *
from litex.soc.cores import frequency_meter
from migen.build.xilinx import XilinxPlatform
from migen.genlib.cdc import MultiReg, PulseSynchronizer, BusSynchronizer
from migen.genlib.cdc import AsyncResetSynchronizer
from migen.genlib.misc import WaitTimer, timeline
path.append("..")
from general import *


class Acquisition(Module):
    def __init__(self):
        pass

if __name__ == '__main__':
    ''' generate a .v file for simulation with Icarus / general usage '''
    from migen.fhdl.verilog import convert
    f_enc = 125e6
    S = 8
    DCO_PERIOD = 1 / (f_enc) * 1e9
    print("f_enc:", f_enc)
    print("DCO_PERIOD:", DCO_PERIOD)
    d = IserdesSp6(S=S, D=1, M=8, DCO_PERIOD=DCO_PERIOD)
    convert(
        d,
        ios={

        },
        display_run=True
    ).write(argv[0].replace(".py", ".v"))
