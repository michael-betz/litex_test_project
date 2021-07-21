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

    ("eth", 0,
        Subsignal("rst_n", Pins("B9"), IOStandard("LVCMOS25")),
        Subsignal("rx_ctl", Pins("J11"), IOStandard("LVCMOS25")),
        Subsignal("rx_data", Pins("J10 J8 H8 H9"), IOStandard("LVCMOS25")),
        Subsignal("tx_ctl", Pins("C9"), IOStandard("LVCMOS25")),
        Subsignal("tx_data", Pins("H11 H12 D8 D9"), IOStandard("LVCMOS25")),
    ),
    ("eth_clocks", 0,
        Subsignal("tx", Pins("F10"), IOStandard("LVCMOS25")),
        Subsignal("rx", Pins("E11"), IOStandard("LVCMOS25")),
    ),
    # PCB bug: Tunable VCXO connected to non clock-capable pin :(
    ("clk20", 0, Pins("W11"), IOStandard("LVCMOS15")),
    ("clk125", 0,
        Subsignal("p", Pins("AC9"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("AD9"), IOStandard("DIFF_SSTL15")),
    ),
    # 4x Multi gigabit clocks from cross-point switch, source configured by MMC
    ("clkmgt0", 0,
        Subsignal("p", Pins("D6"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("D5"), IOStandard("DIFF_SSTL15")),
    ),
    ("clkmgt1", 0,
        Subsignal("p", Pins("F6"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("F5"), IOStandard("DIFF_SSTL15")),
    ),
    ("clkmgt2", 0,
        Subsignal("p", Pins("H6"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("H5"), IOStandard("DIFF_SSTL15")),
    ),
    ("clkmgt3", 0,
        Subsignal("p", Pins("K6"), IOStandard("DIFF_SSTL15")),
        Subsignal("n", Pins("K5"), IOStandard("DIFF_SSTL15")),
    ),
    # 2x LED: LD16 and LD17
    ("user_led", 0, Pins("Y13"), IOStandard("LVCMOS15")),
    ("user_led", 1, Pins("V12"), IOStandard("LVCMOS15")),
    # USB UART
    ("serial", 0,
        Subsignal("tx", Pins("K15"), IOStandard("LVCMOS25")),
        Subsignal("rts", Pins("M16"), IOStandard("LVCMOS25")),
        Subsignal("rx", Pins("C16"), IOStandard("LVCMOS25")),
    ),
    # I2C multiplexer for system control
    ("i2c_fpga", 0,
        Subsignal("scl", Pins("B16"), IOStandard("LVCMOS25")),
        Subsignal("sda", Pins("A17"), IOStandard("LVCMOS25")),
        Subsignal("rst", Pins("B19"), IOStandard("LVCMOS25")),
    ),
    # DDR3 module
    ("ddram", 0,
        Subsignal("a", Pins("AC8 AB10 AA9 AA10 AD10 AC12 AB11 AC11 AF13 AE13 AE10 AD11 AA12 AE8 AB12 AD13"), IOStandard("SSTL15")),
        Subsignal("ba", Pins("AF10 AD8 AC13"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("AB7"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("AF8"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("AF9"), IOStandard("SSTL15")),
        Subsignal("cs_n", Pins("AC7"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("AF17 W15 AC19 AA15 AC3 AD4 W1 U7"), IOStandard("SSTL15")),
        Subsignal("dq", Pins("AF20 AF19 AE17 AE15 AD16 AD15 AF15 AF14 V17 Y17 V18 V19 V16 W16 V14 W14 AA20 AD19 AB17 AC17 AA19 AB19 AD18 AC18 AA18 AB16 AA14 AD14 AB15 AA17 AC14 AB14 AD6 AB6 Y6 AC4 AC6 AB4 AA4 Y5 AF2 AE2 AE1 AD1 AE5 AE6 AF3 AE3 AA3 AC2 V2 V1 AB2 Y3 Y2 Y1 W3 V4 U2 U1 V6 V3 U6 U5"), IOStandard("SSTL15")),
        Subsignal("dqs_p", Pins("AE18 W18 AD20 Y15 AA5 AF5 AB1 W6"), IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("AF18 W19 AE20 Y16 AB5 AF4 AC1 W5"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p", Pins("AE12"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("AF12"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke", Pins("AA13"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("AB9"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("Y12"), IOStandard("SSTL15")),
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("FMC1", {
        "CLK0_M2C_N": "E17",
        "CLK0_M2C_P": "F17",
        "CLK1_M2C_N": "D18",
        "CLK1_M2C_P": "E18",
        "LA0_N": "H18",
        "LA0_P": "H17",
        "LA1_N": "F18",
        "LA1_P": "G17",
        "LA2_N": "J20",
        "LA2_P": "K20",
        "LA3_N": "L18",
        "LA3_P": "M17",
        "LA4_N": "G20",
        "LA4_P": "H19",
        "LA5_N": "E20",
        "LA5_P": "F19",
        "LA6_N": "L20",
        "LA6_P": "L19",
        "LA7_N": "D20",
        "LA7_P": "D19",
        "LA8_N": "F20",
        "LA8_P": "G19",
        "LA9_N": "J19",
        "LA9_P": "J18",
        "LA10_N": "G16",
        "LA10_P": "H16",
        "LA11_N": "K18",
        "LA11_P": "L17",
        "LA12_N": "F15",
        "LA12_P": "G15",
        "LA13_N": "D16",
        "LA13_P": "D15",
        "LA14_N": "E16",
        "LA14_P": "E15",
        "LA15_N": "J16",
        "LA15_P": "J15",
        "LA16_N": "K17",
        "LA16_P": "K16",
        "LA17_N": "D10",
        "LA17_P": "E10",
        "LA18_N": "C11",
        "LA18_P": "C12",
        "LA19_N": "G14",
        "LA19_P": "H14",
        "LA20_N": "A15",
        "LA20_P": "B15",
        "LA21_N": "D13",
        "LA21_P": "D14",
        "LA22_N": "A14",
        "LA22_P": "B14",
        "LA23_N": "F12",
        "LA23_P": "G12",
        "LA24_N": "A8",
        "LA24_P": "A9",
        "LA25_N": "G9",
        "LA25_P": "G10",
        "LA26_N": "E12",
        "LA26_P": "E13",
        "LA27_N": "F13",
        "LA27_P": "F14",
        "LA28_N": "H13",
        "LA28_P": "J13",
        "LA29_N": "F8",
        "LA29_P": "F9",
        "LA30_N": "B11",
        "LA30_P": "B12",
        "LA31_N": "A12",
        "LA31_P": "A13",
        "LA32_N": "C13",
        "LA32_P": "C14",
        "LA33_N": "A10",
        "LA33_P": "B10",
    }),
    ("FMC2", {
        "CLK0_M2C_N": "AA24",
        "CLK0_M2C_P": "Y23",
        "CLK1_M2C_N": "E23",
        "CLK1_M2C_P": "F22",
        "HA00_CC_N": "N22",
        "HA00_CC_P": "N21",
        "HA01_CC_N": "P21",
        "HA01_CC_P": "R21",
        "HA02_N": "U20",
        "HA02_P": "U19",
        "HA03_N": "T19",
        "HA03_P": "T18",
        "HA04_N": "R17",
        "HA04_P": "R16",
        "HA05_N": "N17",
        "HA05_P": "P16",
        "HA06_N": "P18",
        "HA06_P": "R18",
        "HA07_N": "T25",
        "HA07_P": "T24",
        "HA08_N": "T23",
        "HA08_P": "T22",
        "HA09_N": "T17",
        "HA09_P": "U17",
        "HA10_N": "K26",
        "HA10_P": "K25",
        "HA11_N": "M19",
        "HA11_P": "N18",
        "HA12_N": "L24",
        "HA12_P": "M24",
        "HA13_N": "R20",
        "HA13_P": "T20",
        "HA14_N": "P20",
        "HA14_P": "P19",
        "HA15_N": "P25",
        "HA15_P": "R25",
        "HA16_N": "P26",
        "HA16_P": "R26",
        "HA17_CC_N": "R23",
        "HA17_CC_P": "R22",
        "HA18_N": "M22",
        "HA18_P": "M21",
        "HA19_N": "M20",
        "HA19_P": "N19",
        "HA20_N": "N23",
        "HA20_P": "P23",
        "HA21_N": "N24",
        "HA21_P": "P24",
        "HA22_N": "M26",
        "HA22_P": "N26",
        "HA23_N": "L25",
        "HA23_P": "M25",
        "LA0_N": "AA22",
        "LA0_P": "Y22",
        "LA1_N": "AB24",
        "LA1_P": "AA23",
        "LA2_N": "AF22",
        "LA2_P": "AE22",
        "LA3_N": "AE26",
        "LA3_P": "AD26",
        "LA4_N": "W21",
        "LA4_P": "V21",
        "LA5_N": "AC26",
        "LA5_P": "AB26",
        "LA6_N": "AD24",
        "LA6_P": "AD23",
        "LA7_N": "AC22",
        "LA7_P": "AB22",
        "LA8_N": "AC24",
        "LA8_P": "AC23",
        "LA9_N": "V26",
        "LA9_P": "U26",
        "LA10_N": "AF23",
        "LA10_P": "AE23",
        "LA11_N": "W24",
        "LA11_P": "W23",
        "LA12_N": "AB25",
        "LA12_P": "AA25",
        "LA13_N": "V24",
        "LA13_P": "V23",
        "LA14_N": "U25",
        "LA14_P": "U24",
        "LA15_N": "V22",
        "LA15_P": "U22",
        "LA16_N": "W26",
        "LA16_P": "W25",
        "LA17_N": "F23",
        "LA17_P": "G22",
        "LA18_N": "F24",
        "LA18_P": "G24",
        "LA19_N": "J23",
        "LA19_P": "K23",
        "LA20_N": "K22",
        "LA20_P": "L22",
        "LA21_N": "H22",
        "LA21_P": "J21",
        "LA22_N": "D25",
        "LA22_P": "E25",
        "LA23_N": "H24",
        "LA23_P": "H23",
        "LA24_N": "J25",
        "LA24_P": "J24",
        "LA25_N": "D24",
        "LA25_P": "D23",
        "LA26_N": "E26",
        "LA26_P": "F25",
        "LA27_N": "G21",
        "LA27_P": "H21",
        "LA28_N": "G26",
        "LA28_P": "G25",
        "LA29_N": "H26",
        "LA29_P": "J26",
        "LA30_N": "C26",
        "LA30_P": "D26",
        "LA31_N": "E22",
        "LA31_P": "E21",
        "LA32_N": "A20",
        "LA32_P": "B20",
        "LA33_N": "B21",
        "LA33_P": "C21",
    }),
    ("pmod1", "C24 C22 L23 D21 K21 C18 C19 C17"),
    ("pmod2", "AE7 V7 Y7 AF7 V8 AA8 Y8 W9"),
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
            "write_cfgmem -force -format bin -interface spix4 -size 16 -loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"
        ]

        # from pin_map.csv: This is a frequency source, not a phase source, so having it enter on a non-CC pin is OK.
        self.add_platform_command("set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets clk20_IBUF]")
        self.add_platform_command("set_property CONFIG_VOLTAGE 2.5 [current_design]")
        self.add_platform_command("set_property CFGBVS VCCO [current_design]")

        # TODO
        # self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 35]")

    def create_programmer(self):
        return OpenOCD("openocd_marblemini.cfg")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk20", loose=True), 1e9/20e6)
        self.add_period_constraint(self.lookup_request("clk125", loose=True), 1e9/125e6)
