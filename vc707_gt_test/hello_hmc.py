"""
Runs on a Zedboard (Zynq)

quick hack to access the 3 wire SPI interface of HMC7044 on the
AD9174-FMC-EBZ card.

try:
 python3 hello_HMC.py <build / synth / config>
"""
from migen import *
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna
from litex.boards.platforms import zedboard
from sys import path
path.append("..")
from common import main
from zedboard import spi


# create our soc (no cpu, only wishbone 2 mem_map bridge)
class HelloHmc(SoCZynq, AutoCSR):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "lvds",
        "acq",
        "analyzer"
    ]
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    def __init__(self, clk_freq, **kwargs):
        print("Hello_hmc: ", kwargs)
        SoCZynq.__init__(
            self,
            clk_freq=clk_freq,
            ps7_name="processing_system7_0",
            # cpu_type=None,
            csr_data_width=32,
            # csr_address_width=16,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="HMC7044 spi bvridge", ident_version=True,
            **kwargs
        )
        self.clock_domains.cd_sys = ClockDomain()
        # sys_clk is provided by FCLK_CLK0 from PS7
        p = self.platform
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)

        p.add_extension([
            ("AD9174_SPI", 0,
                # FMC_CS1 (AD9174), FMC_CS2 (HMC7044)
                Subsignal("cs_n", Pins("LPC:LA04_N LPC:LA05_P")),
                Subsignal("miso", Pins("LPC:LA04_P"), Misc("PULLUP TRUE")),
                Subsignal("mosi", Pins("LPC:LA03_N")),
                Subsignal("clk",  Pins("LPC:LA03_P")),
                IOStandard("LVCMOS18")
            ),
        ])
        # self.submodules.crg = _CRG(p, clk_freq)z

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("AD9174_SPI")
        self.submodules.spi = spi.SPIMaster(
            spi_pads,
            # 16,
            # self.clk_freq,
            # int(1e6)
        )


if __name__ == '__main__':
    soc = HelloHmc(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP, Clock Configuration --> PL Fabric Clocks --> FCLK_CLK0
        clk_freq=int(100e6)
    )
    vns = main(soc, doc=__doc__)
