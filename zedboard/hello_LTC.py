"""
Runs on a Zedboard (Zynq)

The Programmable Logic (PL) interfaces to an LTC2175 through 8 LVDS lanes.
It uses the UARTWishboneBridge and a FTDI cable to make its litex
CSR's accessible.

The Processing System (PS) runs debian and can re-program the PL with a
.bit.bin file

They do speak to each other through litex CSRs and `comm_devmem.py`.

try:
 python3 hello_LTC.py <build / synth / config>
"""
from migen import *
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_zynq import *
from litex.soc.integration.builder import *
from migen.genlib.cdc import MultiReg
from litex.soc.cores import dna, uart, spi_old
from litex.boards.platforms import zedboard
from litex.soc.cores.clock import S7MMCM, S7IDELAYCTRL
from litex.soc.interconnect import wishbone
from litescope import LiteScopeAnalyzer
from sys import path
path.append("iserdes")
from ltc_phy import LTCPhy
path.append("..")
from common import main, ltc_pads
path.append("../sp605/dsp")
from acquisition import Acquisition


class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add("keep")

        self.submodules.pll = pll = S7MMCM(speedgrade=-1)
        pll.register_clkin(ClockSignal(), 100e6)
        self.comb += [
            pll.reset.eq(ResetSignal()),
            platform.request("user_led").eq(pll.locked)
        ]

        pll.create_clkout(self.cd_clk200, 200e6)
        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

        # sys_clk is provided by FCLK_CLK0 from PS7
        # pll.create_clkout(self.cd_sys, sys_clk_freq)



# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCZynq, AutoCSR):
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
        print("HelloLtc: ", kwargs)
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
            ident="LTC2175 demonstrator", ident_version=True,
            **kwargs
        )
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)

        p = self.platform
        p.add_extension(ltc_pads)
        self.submodules.crg = _CRG(p, clk_freq)

        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        # connect FTDI cable to PMOD JA1
        # p.add_extension([(
        #     "serial", 0,
        #     Subsignal("tx", Pins("pmoda:0")),
        #     Subsignal("rx", Pins("pmoda:4")),
        #     IOStandard("LVCMOS33")
        # )])
        # self.add_cpu(uart.UARTWishboneBridge(
        #     p.request("serial"),
        #     clk_freq,
        #     baudrate=1152000
        # ))
        # self.add_wb_master(self.cpu.wishbone)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  LTC LVDS driver on FMC LPC
        # ----------------------------
        # LTCPhy will recover ADC clock and drive `sample` clock domain
        self.submodules.lvds = LTCPhy(p, clk_freq)

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("LTC_SPI")
        self.submodules.spi = spi_old.SPIMaster(spi_pads)

        # ----------------------------
        #  Acquisition memory for ADC data
        # ----------------------------
        # mems = []
        # for i, sample_out in enumerate(self.lvds.sample_outs):
        mem = Memory(16, 4096, init=[0, 0xDEAD, 0xBEEF, 0xC0FE, 0xAFFE])
        #     mems.append(mem)
        self.specials += mem
        self.submodules.sample_ram = wishbone.SRAM(mem, read_only=False)
        self.register_mem(
            "sample{}".format(0),
            0x10000000 + 0 * 0x1000000,
            self.sample_ram.bus,
            mem.depth
        )
            # p2 = mem.get_port(write_capable=True, clock_domain="sample")
            # self.specials += p2
            # self.sync.sample += [
            #     p2.we.eq(1),
            #     p2.adr.eq(p2.adr + 1),
            #     p2.dat_w.eq(sample_out)
            # ]
        # self.submodules.acq = Acquisition(mems, self.lvds.sample_outs, N_BITS=16)
        # self.specials += MultiReg(
        #     p.request("user_btn_d"), self.acq.trigger
        # )
        # self.comb += [
        #     p.request("user_led").eq(self.acq.trigger),
        #     p.request("user_led").eq(self.acq.busy)
        # ]

if __name__ == '__main__':
    soc = HelloLtc(
        platform=zedboard.Platform(),
        # Needs to match Vivado IP, Clock Configuration --> PL Fabric Clocks --> FCLK_CLK0
        clk_freq=int(100e6)
    )
    vns = main(soc, doc=__doc__)
