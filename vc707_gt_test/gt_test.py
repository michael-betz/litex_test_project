"""
AD9174-FMC-EBZ board on VC707

See if we can receive a 128 MHz clock from
HMC7044 through the FMC (on GBTCLK0_M2C)

Demonstrate by blinking a LED

try:
  python3 gl_test.py <build / synth / config>
"""
from migen import *
from collections import namedtuple
from migen.genlib.io import DifferentialOutput, DifferentialInput
from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc
from litex.soc.cores import dna, uart, spi, freqmeter
from litex.soc.interconnect.csr import AutoCSR
from litex.soc.integration.soc_core import SoCCore
from jesd204b.phy.gtx import GTXQuadPLL
from jesd204b.phy import JESD204BPhyTX
from jesd204b.common import JESD204BPhysicalSettings, JESD204BTransportSettings, JESD204BSettings
from jesd204b.core import JESD204BCoreTX, JESD204BCoreTXControl
from litex.soc.interconnect.csr import CSRStorage
from litescope import LiteScopeIO, LiteScopeAnalyzer
from xdc import vc707
from sys import path
path.append("..")
from common import main


class CRG(Module, AutoCSR):
    def __init__(self, p, serd_pads, add_rst=[]):
        '''
        add_rst = additional reset signals for sys_clk
          must be active high and will be synchronized with sys_clk
        '''
        self.clock_domains.cd_sys = ClockDomain()

        self.sys_clk_freq = int(1e9 / p.default_clk_period)
        # depends on AD9174 JESD / DAC interpolation settings
        self.gtx_line_freq = int(6.4e9)
        # depends on f_wenzel and dividers in AD9174 + HMC7044
        self.tx_clk_freq = int(5.12e9 / 4 / 8)

        # # #

        clk_pads = p.request(p.default_clk_name)
        self.specials += DifferentialInput(
            clk_pads.p, clk_pads.n, self.cd_sys.clk
        )

        rst_sum = Signal()
        self.comb += rst_sum.eq(reduce(or_, add_rst))
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst_sum)

        # Handle the GTX clock input
        refclk0 = Signal()
        self.specials += Instance(
            "IBUFDS_GTE2",
            i_CEB=0,
            i_I=serd_pads.clk_p,
            i_IB=serd_pads.clk_n,
            o_O=refclk0
        )
        self.clock_domains.cd_jesd = ClockDomain()
        self.specials += [
            Instance("BUFG", i_I=refclk0, o_O=self.cd_jesd.clk),
            AsyncResetSynchronizer(self.cd_jesd, ResetSignal('sys'))  # self.jreset.storage)
        ]

        # Add a frequency counter to `cd_jesd` (128 MHz) measures in [Hz]
        self.submodules.f_jesd = freqmeter.FreqMeter(
            self.sys_clk_freq,
            clk=ClockSignal('jesd')
        )

        self.submodules.qpll0 = GTXQuadPLL(
            refclk0,
            self.tx_clk_freq,
            self.gtx_line_freq
        )
        print(self.qpll0)


class GtTest(SoCCore):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "crg",
        "control",
        "phy0",
        "phy1",
        "phy2",
        "phy3",
        "f_ref"
    ]

    def __init__(self, p, **kwargs):
        print("GtTest: ", p, kwargs)

        # ----------------------------
        #  Litex config
        # ----------------------------
        SoCCore.__init__(
            self,
            clk_freq=int(1e9 / p.default_clk_period),
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="AD9174 + VC707 test", ident_version=True,
            platform=p,
            **kwargs
        )
        for c in GtTest.csr_peripherals:
            self.add_csr(c)

        # ----------------------------
        #  Ports
        # ----------------------------
        N_LANES = 1
        p.add_extension([
            ("AD9174_JESD204", 0,
                # CLK comes from HMC7044 CLKOUT12, goes to GTX (128 MHz)
                Subsignal("clk_p", Pins("FMC1_HPC:GBTCLK0_M2C_C_P")),
                Subsignal("clk_n", Pins("FMC1_HPC:GBTCLK0_M2C_C_N")),

                # GTX data lanes
                # on `AD9172_FMC_EBZ` SERDIN 0 - 3 are of __inverted__ polarity!
                Subsignal("tx_p",  Pins(" ".join(
                    ["FMC1_HPC:DP{}_C2M_P".format(i) for i in [5, 6, 4, 7, 3, 2, 1, 0][:N_LANES]]
                ))),
                Subsignal("tx_n",  Pins(" ".join(
                    ["FMC1_HPC:DP{}_C2M_N".format(i) for i in [5, 6, 4, 7, 3, 2, 1, 0][:N_LANES]]
                ))),

                # JSYNC comes from AD9174 SYNC_OUT_0B, SYNC_OUT_1B
                Subsignal("jsync0_p", Pins("FMC1_HPC:LA01_CC_P"), IOStandard("LVDS")),
                Subsignal("jsync0_n", Pins("FMC1_HPC:LA01_CC_N"), IOStandard("LVDS")),

                # Subsignal("jsync1_p", Pins("FMC1_HPC:LA02_P"), IOStandard("LVDS")),
                # Subsignal("jsync1_n", Pins("FMC1_HPC:LA02_N"), IOStandard("LVDS")),

                # SYSREF comes from HMC7044 CLKOUT13 (16 MHz)
                Subsignal("sysref_p", Pins("FMC1_HPC:LA00_CC_P"), IOStandard("LVDS")),
                Subsignal("sysref_n", Pins("FMC1_HPC:LA00_CC_N"), IOStandard("LVDS"))
            ),
            ("AD9174_SPI", 0,
                # FMC_CS1 (AD9174), FMC_CS2 (HMC7044)
                Subsignal("cs_n", Pins("FMC1_HPC:LA04_N FMC1_HPC:LA05_P")),
                Subsignal("miso", Pins("FMC1_HPC:LA04_P"), Misc("PULLUP TRUE")),
                Subsignal("mosi", Pins("FMC1_HPC:LA03_N")),
                Subsignal("clk",  Pins("FMC1_HPC:LA03_P")),
                Subsignal("spi_en", Pins("FMC1_HPC:LA05_N")),
                IOStandard("LVCMOS18")
            ),
        ])
        TxPNTuple = namedtuple("TxPN", "txp txn")
        serd_pads = p.request("AD9174_JESD204")

        self.submodules.crg = CRG(p, serd_pads, [self.ctrl.reset])

        # ----------------------------
        #  GTX phy
        # ----------------------------
        # 1 JESD204BPhyTX with its own `TX<N>` clock domain for each lane
        phys = []
        for i, (tx_p, tx_n) in enumerate(zip(serd_pads.tx_p, serd_pads.tx_n)):
            phy = JESD204BPhyTX(
                self.crg.qpll0,
                TxPNTuple(tx_p, tx_n),
                self.crg.sys_clk_freq,
                transceiver="gtx",
                polarity=1
            )
            p.add_period_constraint(
                phy.transmitter.cd_tx.clk,
                1e9 / self.crg.tx_clk_freq
            )
            # Tell vivado the clocks are async
            p.add_false_path_constraints(
                self.crg.cd_sys.clk,
                phy.transmitter.cd_tx.clk
            )
            phys.append(phy)
            setattr(self, 'phy{}'.format(i), phy)

        # Mode 0 (L = 1, M = 2, F = 4, S = 1, NP = 16, N = 16)
        # 1 lane, 2 converters (I0, Q0), 4 byte / frame, 1 sample / frame, 16 bit
        # 32 bit / frame = 1 sample, 128 MSps from FPGA, DAC at 4.096 GSps?
        ps = JESD204BPhysicalSettings(l=1, m=2, n=16, np=16, subclassv=1)
        ts = JESD204BTransportSettings(f=4, s=1, k=32, cs=0)
        settings = JESD204BSettings(ps, ts, did=0x5a, bid=0x05, hd=4)

        self.submodules.core = JESD204BCoreTX(
            phys,
            settings,
            converter_data_width=16
        )
        self.submodules.control = JESD204BCoreTXControl(self.core)

        jsync = Signal()
        self.specials += DifferentialInput(
            serd_pads.jsync0_p, serd_pads.jsync0_n, jsync
        )
        self.core.register_jsync(jsync)
        self.comb += p.request('user_led').eq(jsync)

        j_ref = Signal()
        self.specials += DifferentialInput(
            serd_pads.sysref_p, serd_pads.sysref_n, j_ref
        )
        self.core.register_jref(j_ref)
        self.submodules.f_ref = freqmeter.FreqMeter(
            self.sys_clk_freq,
            clk=j_ref
        )

        # ----------------------------
        #  Clock blinkers
        # ----------------------------
        # 156.25 MHz / 2**26 = 2.33 Hz
        counter0 = Signal(26)
        self.sync += counter0.eq(counter0 + 1)
        self.comb += p.request("user_led").eq(counter0[-1])

        # 125.00 MHz / 2**26 = 1.86 Hz
        counter1 = Signal(26)
        self.sync.jesd += counter1.eq(counter1 + 1)
        self.comb += p.request("user_led").eq(counter1[-1])

        # To observe 128 MHz clock on scope ...
        sma = p.request("user_sma_gpio_p")
        self.comb += sma.eq(ClockSignal('jesd'))
        # self.specials += DifferentialOutput(ClockSignal('tx'), sma.p, sma.n)
        # tell Vivado it's okay to cross the clock region in a sketchy way
        # p.add_platform_command('set_property CLOCK_DEDICATED_ROUTE ANY_CMT_COLUMN [get_nets refclk0]')
        # self.specials += DifferentialInput(
        #     serd_pads.sysref_p,
        #     serd_pads.sysref_n,
        #     p.request("user_sma_gpio_n")
        # )

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("AD9174_SPI")
        self.comb += spi_pads.spi_en.eq(0)
        self.submodules.spi = spi.SPIMaster(
            spi_pads,
            32,
            self.clk_freq,
            int(1e6)
        )

        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        self.submodules.uart = uart.UARTWishboneBridge(
            p.request("serial"),
            self.clk_freq,
            baudrate=1152000
        )
        self.add_wb_master(self.uart.wishbone)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # Analyzer
        analyzer_groups = {
            0: [
                j_ref,
                self.core.ready,
                self.core.jsync_jesd,
                self.core.jsync_sys,
                self.core.phy_done,
                self.core.link0.fsm,
                self.core.link0.jref_rising,
                self.core.link0.source.data,
                self.core.link0.source.ctrl
            ]
        }
        self.submodules.analyzer = LiteScopeAnalyzer(
            analyzer_groups,
            4096,
            csr_csv="build/analyzer.csv",
            clock_domain='jesd'
        )
        self.add_csr("analyzer")


if __name__ == '__main__':
    soc = GtTest(vc707.Platform())
    main(soc, doc=__doc__)
