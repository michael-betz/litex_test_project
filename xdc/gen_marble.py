'''
generates marble.py litex platform file

usage:
$ python3 gen_marble.py Marble.xdc > marble.py

The Marble.xdc file was auto-generated from the Kicad Schematic netlist.
It's included in the bedrock repo:
https://github.com/BerkeleyLab/Bedrock/raw/master/board_support/marble/Marble.xdc

TODO: QSFP+ transceivers
'''
from sys import argv
from xdc_parser import XdcParser

if len(argv) != 2:
    print(__doc__)
    exit()

p = XdcParser(argv[1])

print('''\
#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2021 Vamsi K Vytla <vamsi.vytla@gmail.com>
# Copyright (c) 2021 Michael Betz <michibetz@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
#
# Marble is a dual FMC FPGA carrier board developed for general purpose use in
# particle accelerator electronics instrumentation. It is currently under
# development and the base platform for two accelerator projects at DOE: ALS-U
# (the Advanced Light Source Upgrade at LBNL and the LCLS-II HE (the Linac
# Coherent Light Source II High Energy upgrade).
# https://github.com/BerkeleyLab/Marble
#
# Generated by gen_marble.py:
# https://github.com/yetifrisstlama/litex_test_project/blob/master/xdc/gen_marble.py
# Pin numbers extracted from a .xdc file, which was auto-generated from
# the Kicad Schematic.

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.openocd import OpenOCD

# IOs ----------------------------------------------------------------------------------------------

_io = [
'''.format(*argv), end='')

p.getGroup('eth', (
    ('rst_n', r'PHY_RSTn'),
    ('rx_ctl', r'RGMII_RX_DV'),
    ('rx_data', r'RGMII_RXD\d'),
    ('tx_ctl', r'RGMII_TX_EN'),
    ('tx_data', r'RGMII_TXD\d')
))

p.getGroup('eth_clocks', (
    ('tx', r'RGMII_TX_CLK'),
    ('rx', r'RGMII_RX_CLK')
))

print('    # Tunable VCXO. Warning: Non clock-capable pin')
p.getGpios('clk20', 'CLK20_VCXO')

print('    # Main system clock. White rabbit compatible')
p.getGroup('clk125', (
    ('p', 'DDR_REF_CLK_C_P'),
    ('n', 'DDR_REF_CLK_C_N'),
))

print('    # 4x Multi gigabit clocks from cross-point switch, source configured by MMC')
for i in range(4):
    p.getGroup('clkmgt', index=i, tuples=(
        ('p', f'MGT_CLK_{i}_P'),
        ('n', f'MGT_CLK_{i}_N'),
    ))

print('    # 2x LED: LD16 and LD17')
p.getGpios('user_led', r'LD1[67]')

print('    # USB UART')
p.getGroup('serial', (
    ('tx', 'FPGA_RxD'),
    ('rts', 'FPGA_RTS'),
    ('rx', 'FPGA_TxD'),
))

print('    # I2C system bus, shared access with microcontroller')
print('    # connected to TCA9548A I2C-multiplexer')
p.getGroup('i2c_fpga', (
    ('scl', 'I2C_FPGA_SCL'),
    ('sda', 'I2C_FPGA_SDA'),
    ('rst', 'I2C_FPGA_SW_RST'),
))

print('    # QSPI Boot Flash')
print('    # access clock via STARTUPE2 primitive, wp_n may not be connected.')
p.getGroup('spiflash', (
    ('cs_n', 'CFG_FCS'),
    ('mosi', 'CFG_MOSI'),
    ('miso', 'CFG_DIN'),
    ('wp_n', 'CFG_D02')
))

print('    # 2x DAC for white rabbit frequency control')
p.getGroup('wr_dac', (
    ('clk', 'WR_DAC_SCLK'),
    ('din', 'WR_DAC_DIN'),
    ('synca', 'WR_DAC1_SYNC'),
    ('syncb', 'WR_DAC2_SYNC')
))

print('    # DDR3 module')
p.getGroup('ddram', (
    ('a', r'DDR3_A\d+', 16),
    ('ba', r'DDR3_BA\d', 3),
    ('ras_n', 'DDR3_RAS_N'),
    ('cas_n', 'DDR3_CAS_N'),
    ('we_n', 'DDR3_WE_N'),
    ('cs_n', r'DDR3_CS_N'),
    ('dm', r'DDR3_DM\d', 8),
    ('dq', r'DDR3_DQ\d+', 64),
    ('dqs_p', r'DDR3_DQS\d_P', 8),
    ('dqs_n', r'DDR3_DQS\d_N', 8),
    ('clk_p', r'DDR3_CK_P'),
    ('clk_n', r'DDR3_CK_N'),
    ('cke', r'DDR3_CKE'),
    ('odt', r'DDR3_ODT'),
    ('reset_n', 'DDR3_RST_N'),
))

print('''\
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
''', end='')

p.getConnector('FMC1', outName='fmca', pinReplace=(('LA_', 'LA'),))
p.getConnector('FMC2', outName='fmcb', pinReplace=(('LA_', 'LA'),))

for i, letter in zip((1, 2), ('a', 'b')):
    p.getConnector(f'Pmod{i}', noKeys=True, outName=f'pmod{letter}')

print('''\
]


# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk125"
    default_clk_period = 1e9 / 125e6

    def __init__(self):
        XilinxPlatform.__init__(self, "xc7k160t-ffg676-2", _io, _connectors, toolchain="vivado")
        self.toolchain.bitstream_commands = [
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"
        ]
        self.toolchain.additional_commands = [
            "write_cfgmem -force -format bin -interface spix4 -size 16 -loadbit \\"up 0x0 {build_name}.bit\\" -file {build_name}.bin"
        ]

        # from pin_map.csv: This is a frequency source, not a phase source, so having it enter on a non-CC pin is OK.
        self.add_platform_command("set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets clk20_IBUF]")
        self.add_platform_command("set_property CONFIG_VOLTAGE 2.5 [current_design]")
        self.add_platform_command("set_property CFGBVS VCCO [current_design]")

        # TODO
        # self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 35]")

    def create_programmer(self):
        # same file works for marble mini and for marble
        return OpenOCD("openocd_marblemini.cfg")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk20", loose=True), 1e9/20e6)
        self.add_period_constraint(self.lookup_request("clk125", loose=True), 1e9/125e6)
''', end='')
