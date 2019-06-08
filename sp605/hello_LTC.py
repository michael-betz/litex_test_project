"""
Trying to communicate with the LTC2175 chip on a
FMC board trough SPI over UartWishbone Bridge
... wish me luck :p

okay, this works, next step: connect to the LVDS FRAME(_P/N)
signal and measure its frequency, which is sample rate / 2 due to DDR:
f_frame = f_enc / 2

try:
 python3 hello_LTC.py <build / synth / config>
"""
from migen import *
from migen.genlib.io import DifferentialOutput, DifferentialInput
from migen.genlib.cdc import MultiReg
from litex.boards.platforms import sp605
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.interconnect.wishbone import SRAM
from liteeth.phy import LiteEthPHY
from liteeth.core import LiteEthUDPIPCore
from liteeth.common import convert_ip
from liteeth.frontend.etherbone import LiteEthEtherbone
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart, spi
from litex.soc.cores.clock import S6PLL
# from sp605_crg import SP605_CRG
from sys import argv, exit, path
from shutil import copyfile
from dsp.acquisition import Acquisition
path.append("..")
path.append("iserdes")
from common import main, ltc_pads
from ltc_phy import LTCPhy


class _CRG(Module):
    def __init__(self, p, sys_clk_freq, f_sample_tx=None):
        # ----------------------------
        #  Clock and Reset Generation
        # ----------------------------
        xtal_pads = p.request(p.default_clk_name)
        xtal = Signal()
        self.specials += DifferentialInput(xtal_pads.p, xtal_pads.n, xtal)
        xtal_f = 1e9 / p.default_clk_period
        rst = p.request("cpu_reset")
        cds = [("cd_sys", sys_clk_freq)]
        if f_sample_tx is not None:
            cds.append(("cd_sample_tx", f_sample_tx))
        for cd, f in cds:
            setattr(self.clock_domains, cd, ClockDomain(cd))
            pll = S6PLL(speedgrade=-3)
            self.comb += pll.reset.eq(rst)
            pll.register_clkin(xtal, xtal_f)
            pll.create_clkout(getattr(self, cd), f)
            self.submodules += pll
        if f_sample_tx is not None:
            # Provide a ENC clock signal on SMA_GPIO
            enc_out = Signal()
            self.specials += Instance(
                "ODDR2",
                o_Q=enc_out,
                i_C0=ClockSignal("sample_tx"),
                i_C1=~ClockSignal("sample_tx"),
                i_CE=1,
                i_D0=1,
                i_D1=0
            )
            p.add_extension(
                # Connect GPIO_SMA on SP605 with CLK input on 1525A
                [("ENC_CLK", 0,
                    Subsignal("p", Pins("SMA_GPIO:P")),
                    Subsignal("n", Pins("SMA_GPIO:N")),
                    # Note: the LTC eval board needs to be modded
                    # to accept a differential clock
                    IOStandard("LVDS_25")
                )]
            )
            gpio_pads = p.request("ENC_CLK")
            self.specials += DifferentialOutput(enc_out, gpio_pads.p, gpio_pads.n)


# create our soc (no cpu, only wishbone 2 serial)
class HelloLtc(SoCCore, AutoCSR):
    # Peripherals CSR declaration
    csr_peripherals = [
        "dna",
        "spi",
        "lvds",
        "acq"
    ]
    csr_map_update(SoCCore.csr_map, csr_peripherals)

    def __init__(self, clk_freq, sample_tx_freq, **kwargs):
        print("HelloLtc: ", kwargs)
        SoCCore.__init__(
            self,
            clk_freq=clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            integrated_sram_size=0,
            ident="LTC2175 demonstrator", ident_version=True,
            **kwargs
        )
        p = self.platform
        self.submodules.crg = _CRG(p, clk_freq, sample_tx_freq)

        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        self.add_cpu(uart.UARTWishboneBridge(
            p.request("serial"),
            clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  FMC LPC connectivity & LTC LVDS driver
        # ----------------------------
        # LTCPhy will recover ADC clock and drive `sample` clock domain
        p.add_extension(ltc_pads)
        self.submodules.lvds = LTCPhy(p, sample_tx_freq)

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = p.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)

        # ----------------------------
        #  Acquisition memory for ADC data
        # ----------------------------
        mem = Memory(16, 4096)
        self.specials += mem
        self.submodules.sample_ram = SRAM(mem, read_only=True)
        self.register_mem("sample", 0x50000000, self.sample_ram.bus, 4096)
        self.submodules.acq = Acquisition([mem])
        self.specials += MultiReg(
            p.request("user_btn"), self.acq.trigger
        )
        self.comb += [
            p.request("user_led").eq(self.acq.busy),
            self.acq.data_ins[0].eq(self.lvds.sample_out),
        ]


# Add etherbone support
class HelloLtcEth(HelloLtc):
    csr_map_update(SoCCore.csr_map, ["ethphy"])

    def __init__(self, **kwargs):
        HelloLtc.__init__(self, **kwargs)
        p = self.platform
        # ethernet PHY and UDP/IP stack
        mac_address = 0x01E625688D7C
        ip_address = "192.168.1.50"
        self.submodules.ethphy = LiteEthPHY(
            p.request("eth_clocks"),
            p.request("eth"),
            self.clk_freq,
            # avoid huge reset delay in simulation
            with_hw_init_reset="synth" in argv
        )
        self.submodules.core = LiteEthUDPIPCore(
            self.ethphy, mac_address, convert_ip(ip_address), self.clk_freq
        )
        # Etherbone = wishbone master = read and write registers remotely
        self.submodules.etherbone = LiteEthEtherbone(
            self.core.udp, 1234, mode="master"
        )
        self.add_wb_master(self.etherbone.wishbone.bus)


if __name__ == '__main__':
    # clk_freq should be >= 125 MHz for ethernet !!!
    soc = HelloLtcEth(
        platform=sp605.Platform(),
        clk_freq=int(125e6),
        sample_tx_freq=int(120e6)
    )
    main(soc, doc=__doc__)
