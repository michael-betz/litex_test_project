"""
Runs on a Zedboard (Zynq)

Test the new i2c master

try:
 python3 hello_i2c.py <build / synth / config>
"""
from migen import *
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, spi
from litex.boards.platforms import zedboard
from sys import path
path.append("../i2c")
from i2c import I2CMaster
path.append("..")
from common import main


# create our soc (no cpu, only wishbone 2 mem_map bridge)
class HelloI2c(SoCZynq, AutoCSR):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "i2c",
        "analyzer"
    ]

    def __init__(self, f_sys, **kwargs):
        print("Hello_i2c: ", kwargs)
        SoCZynq.__init__(
            self,
            clk_freq=f_sys,
            ps7_name="processing_system7_0",
            # cpu_type=None,
            csr_data_width=32,
            # csr_address_width=16,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="I2C test", ident_version=True,
            **kwargs
        )
        for c in HelloI2c.csr_peripherals:
            self.add_csr(c)
        self.clock_domains.cd_sys = ClockDomain()
        # sys_clk is provided by FCLK_CLK0 from PS7
        p = self.platform
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x40000000)

        p.add_extension([(
            "SI570_I2C",
            0,
            Subsignal("oe", Pins("pmodb:5")),
            Subsignal("scl", Pins("pmodb:6")),
            Subsignal("sda", Pins("pmodb:7")),
            IOStandard("LVCMOS33")
        )])

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  I2C master
        # ----------------------------
        # Connect Si570 (sample clk) to I2C master
        si570_pads = p.request("SI570_I2C")
        self.submodules.i2c = I2CMaster(f_sys)
        self.i2c.add_pads(si570_pads)
        self.i2c.add_csr()
        self.si570_oe = CSRStorage(1, reset=1)
        self.comb += si570_pads.oe.eq(self.si570_oe.storage)

        # ----------------------------
        #  Logic analyzer
        # ----------------------------
        from litescope import LiteScopeAnalyzer
        debug = [
            si570_pads.sda,
            si570_pads.scl,
            self.i2c.start,
            self.i2c.done,
            self.i2c.mode,
            self.i2c.clk_rise,
            self.i2c.clk_fall,
            self.i2c.clk_divider,
            self.i2c.bits
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(debug, 4096)

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "build/analyzer.csv")


if __name__ == '__main__':
    soc = HelloI2c(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP, Clock Configuration --> PL Fabric Clocks --> FCLK_CLK0
        f_sys=int(100e6)
    )
    vns = main(soc, doc=__doc__)
