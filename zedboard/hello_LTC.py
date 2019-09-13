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
from migen.genlib.resetsync import AsyncResetSynchronizer
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
    def __init__(self, platform, sys_clk_freq, add_rst=None):
        '''
        add_rst = additional reset signals for sys_clk
          must be active high and will be synchronized with sys_clk
        '''
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_clk200 = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add('keep')

        self.submodules.pll = pll = S7MMCM(speedgrade=-1)
        pll.register_clkin(ClockSignal('sys'), 100e6)
        self.comb += [
            pll.reset.eq(ResetSignal('sys')),
            platform.request('user_led').eq(pll.locked)
        ]

        pll.create_clkout(self.cd_clk200, 200e6)
        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

        rst_sum = Signal()
        if add_rst is not None:
            self.comb += rst_sum.eq(platform.request('user_btn_u') | add_rst)
        else:
            self.comb += rst_sum.eq(platform.request('user_btn_u'))
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst_sum)
        self.comb += platform.request('user_led').eq(ResetSignal('sys'))
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
            add_reset=False,
            **kwargs
        )
        p = self.platform
        self.add_gp0()
        self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)

        self.submodules.crg = _CRG(
            p,
            clk_freq,
            ~self.fclk_reset0_n
        )

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  LTC LVDS driver on FMC LPC
        # ----------------------------
        p.add_extension(ltc_pads)
        # LTCPhy will recover ADC clock and drive `sample` clock domain
        self.submodules.lvds = LTCPhy(p, clk_freq)
        # tell vivado that sys_clk and sampl_clk are asynchronous
        p.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.lvds.pads_dco.p
        )

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("LTC_SPI")
        self.submodules.spi = spi_old.SPIMaster(spi_pads)

        # ----------------------------
        #  Acquisition memory for ADC data
        # ----------------------------
        mems = []
        btn_c = p.request('user_btn_c')
        for i, sample_out in enumerate(self.lvds.sample_outs):
            mem = Memory(16, 4096, init=[i, 0xDEAD, 0xBEEF, 0xC0FE, 0xAFFE])
            mems.append(mem)
            self.specials += mem
            self.submodules.sample_ram = wishbone.SRAM(mem, read_only=True)
            self.register_mem(
                "sample{}".format(i),
                0x10000000 + i * 0x1000000,
                self.sample_ram.bus,
                mem.depth
            )
            p2 = mem.get_port(write_capable=True, clock_domain="sample")
            self.specials += p2
            self.sync.sample += [
                p2.we.eq(btn_c),
                p2.adr.eq(p2.adr + 1),
                p2.dat_w.eq(sample_out)
            ]
            # break
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
