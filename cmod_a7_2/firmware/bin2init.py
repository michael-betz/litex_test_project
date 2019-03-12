"""\
Convert .bin to verilog .mem file and print to stdout
usage: bin2init.py boot.bin little
"""
from litex.soc.integration.soc_core import get_mem_data
from sys import argv
if len(argv) != 3:
    print(__doc__)
else:
    dats = get_mem_data("./boot.bin", "little")
    for dat in dats:
        print("{:08x}".format(dat))
