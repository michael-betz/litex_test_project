'''
debug a memory decoding issue on the wishbone
'''
import sys
sys.path.append('..')
from common import conLitexServer, hd

r = conLitexServer(csr_csv='out/csr.csv', port=1234)

hd(r.read(r.mems.sram.base + 0x000 * 4, 0x80), 2)
hd(r.read(r.mems.sram.base + 0xF80 * 4, 0x80), 2)

# print(hex(r.read(r.mems.sram.base + 0x3FF * 4)))
# print(hex(r.read(r.mems.sram.base + 0x400 * 4)))
