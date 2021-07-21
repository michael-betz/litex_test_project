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
# Copyright (c) 2021 Michael Betz <michibetz@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause


# Marble is a dual FMC FPGA carrier board developed for general purpose use in
# particle accelerator electronics instrumentation. It is currently under
# development and the base platform for two accelerator projects at DOE: ALS-U
# (the Advanced Light Source Upgrade at LBNL and the LCLS-II HE (the Linac
# Coherent Light Source II High Energy upgrade).
# https://github.com/BerkeleyLab/Marble

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, VivadoProgrammer
from litex.build.openocd import OpenOCD

# IOs ----------------------------------------------------------------------------------------------

_io = [

'''.format(*argv), end='')

p.getGroup('eth', (
    ('rst_n', r'PHY_RSTn'),
    ('rx_dv', r'RGMII_RX_DV'),
    ('rx_data', r'RGMII_RXD\d'),
    ('tx_en', r'RGMII_TX_EN'),
    ('tx_data', r'RGMII_RXD\d')
))

# Tunable VCXO
p.getGroup('clk20', (
    ('p', 'CLK20_VCXO'),
))

p.getGroup('clk125', (
    ('p', 'DDR_REF_CLK_C_P'),
    ('n', 'DDR_REF_CLK_C_N'),
))

# 4x Multi gigabit clocks from cross-point switch, source configured by MMC
for i in range(4):
    p.getGroup(f'clkmgt{i}', (
        ('p', f'MGT_CLK_{i}_P'),
        ('n', f'MGT_CLK_{i}_N'),
    ))

# 2x LED: LD16 and LD17
p.getGpios('user_led', r'LD1[67]')

# USB UART
p.getGroup('serial', (
    ('rx', 'FPGA_RxD'),
    ('rts', 'FPGA_RTS'),
    ('tx', 'FPGA_TxD'),
))

# DDR3 module
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

p.getConnector('FMC1', (
    ('LA_', 'LA'),
))

p.getConnector('FMC2', (
    ('LA_', 'LA'),
))

for i in (1, 2):
    p.getConnector(f'Pmod{i}', noKeys=True, outName=f'pmod{i}')

print('''\
]


# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk20"
    default_clk_period = 1e9 / 20e6

    def __init__(self):
        XilinxPlatform.__init__(self, "xc7k160t-ffg676-2", _io, _connectors, toolchain="vivado")
        self.toolchain.bitstream_commands = [
            "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"
        ]
        self.toolchain.additional_commands = [
            "write_cfgmem -force -format bin -interface spix4 -size 16 -loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"
        ]
        self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 35]")
        self.add_platform_command("set_property CFGBVS VCCO [current_design]")
        self.add_platform_command("set_property CONFIG_VOLTAGE 3.3 [current_design]")

    def create_programmer(self):
        return OpenOCD("openocd_marblemini.cfg")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk20", loose=True), 1e9/20e6)
        self.add_period_constraint(self.lookup_request("clk125", loose=True), 1e9/125e6)
''', end='')
