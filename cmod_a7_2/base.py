"""
Target support for the Digilent Cmod A7 Board
Inherit from the BaseSoC class in your design
"""
from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import spi_flash
from litex.soc.cores.clock import period_ns, S7MMCM
import argparse

class _CRG(Module):
    """
    clock and reset generator
    Inherit from this class to make sys_clk adjustable
    """
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        # self.clock_domains.cd_clk200 = ClockDomain()
        self.submodules.mmcm = mmcm = S7MMCM(speedgrade=-1)
        mmcm.register_clkin(platform.request("clk12"), 12e6)
        # create_clkout also takes care of generating BUFG / BUFR instances
        mmcm.create_clkout(self.cd_sys, sys_clk_freq)
        # mmcm.create_clkout(self.cd_clk200, 200e6)
        # self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)


class BaseSoC(SoCCore):
    csr_peripherals = (
        "spiflash"
    )
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    mem_map = {
        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
    }
    mem_map.update(SoCCore.mem_map)

    def __init__(self, platform=None, spiflash="spiflash_1x", **kwargs):
        if platform is None:
            from cmod_a7 import Platform
            platform = Platform()
        elif platform == "sim":
            from litex.build.sim.platform import SimPlatform
            platform = SimPlatform()
        print("platform", platform)
        if 'integrated_rom_size' not in kwargs:
            kwargs['integrated_rom_size'] = 0x8000
        if 'integrated_sram_size' not in kwargs:
            kwargs['integrated_sram_size'] = 0x8000

        sys_clk_freq = int(100e6)
        print(kwargs)
        SoCCore.__init__(self, platform, sys_clk_freq, **kwargs)
        self.submodules.crg = _CRG(platform, sys_clk_freq)
        # self.crg.cd_sys.clk.attr.add("keep")
        # self.platform.add_period_constraint(
        #     self.crg.cd_sys.clk,
        #     period_ns(sys_clk_freq)
        # )

        # spi flash
        spiflash_pads = platform.request(spiflash)
        spiflash_pads.clk = Signal()
        self.specials += Instance(
            "STARTUPE2",
            i_CLK=0, i_GSR=0, i_GTS=0, i_KEYCLEARB=0, i_PACK=0,
            i_USRCCLKO=spiflash_pads.clk, i_USRCCLKTS=0, i_USRDONEO=1,
            i_USRDONETS=1
        )
        spiflash_dummy = {
            "spiflash_1x": 9,
            "spiflash_4x": 11,
        }
        self.submodules.spiflash = spi_flash.SpiFlash(
            spiflash_pads,
            dummy=spiflash_dummy[spiflash],
            div=2
        )
        self.add_constant("SPIFLASH_PAGE_SIZE", 256)
        self.add_constant("SPIFLASH_SECTOR_SIZE", 0x10000)
        self.add_wb_slave(
            mem_decoder(self.mem_map["spiflash"]),
            self.spiflash.bus
        )
        self.add_memory_region(
            "spiflash",
            self.mem_map["spiflash"] | self.shadow_base,
            16 * 1024 * 1024
        )


def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on CmodA7")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()
    print(args)
    soc = BaseSoC(**soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
