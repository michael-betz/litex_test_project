"""
Runs on a Zedboard (Zynq)

The Programmable Logic (PL) interfaces to an LTC2175 through 8 LVDS lanes.
It uses the UARTWishboneBridge and a FTDI cable to make its litex
CSR's accessible.

The Processing System (PS) runs debian and can re-program the PL with a
.bit.bin file

So far they don't speak to each other.

try:
 python3 hello_LTC.py <build / synth / config>
"""
from migen import *
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
# from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart, spi
from litex.boards.platforms import zedboard
from litex.soc.cores.clock import S7MMCM, S7IDELAYCTRL
from sys import path
path.append("..")
from common import main, ltc_pads
from ltc_phy import LTCPhy


class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add("keep")

        self.submodules.pll = pll = S7MMCM(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("user_btn_c"))
        pll.register_clkin(platform.request("clk100"), 100e6)
        # pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_clk200, 200e6)
        self.comb += platform.request("user_led").eq(pll.locked)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCZynq, AutoCSR):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "lvds"
    ]
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    def __init__(self, clk_freq, **kwargs):
        print("HelloLtc: ", kwargs)
        SoCZynq.__init__(
            self,
            clk_freq=clk_freq,
            ps7_name="processing_system7_0",
            # cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="LTC2175 demonstrator", ident_version=True,
            **kwargs
        )
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x43c00000)

        p = self.platform
        p.add_extension(ltc_pads)
        self.submodules.crg = _CRG(p, clk_freq)

        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        # connect FTDI cable to PMOD JA1
        p.add_extension([(
            "serial", 0,
            Subsignal("tx", Pins("pmoda:0")),
            Subsignal("rx", Pins("pmoda:4")),
            IOStandard("LVCMOS33")
        )])
        self.add_cpu(uart.UARTWishboneBridge(
            p.request("serial"),
            clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  LTC LVDS driver on FMC LPC
        # ----------------------------
        # LTCPhy will recover ADC clock and drive `sample` clock domain
        self.submodules.lvds = LTCPhy(p)

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)

        # # ----------------------------
        # #  Acquisition memory for ADC data
        # # ----------------------------
        # mem = Memory(16, 4096)
        # self.specials += mem
        # self.submodules.sample_ram = SRAM(mem, read_only=True)
        # self.register_mem("sample", 0x50000000, self.sample_ram.bus, 4096)
        # self.submodules.acq = Acquisition(mem)
        # self.specials += MultiReg(
        #     p.request("user_btn"), self.acq.trigger
        # )
        # self.comb += [
        #     p.request("user_led").eq(self.acq.busy),
        #     self.acq.data_in.eq(self.lvds.sample_out),
        # ]



if __name__ == '__main__':
    soc = HelloLtc(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP, Clock Configuration --> PL Fabrick Clocks --> FCLK_CLK0
        clk_freq=int(100e6)
    )
    main(soc, doc=__doc__)
    # soc.generate_software_header("csr.h")
