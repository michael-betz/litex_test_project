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
from migen.genlib.io import DifferentialOutput
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
from sp605_crg import SP605_CRG
from sys import argv, exit, path
from shutil import copyfile
from dsp.acquisition import Acquisition
path.append("..")
path.append("iserdes")
from common import main
from ltc_phy import LTCPhy


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

    def __init__(self, **kwargs):
        print("HelloLtc: ", kwargs)
        SoCCore.__init__(
            self,
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
        # ----------------------------
        #  Serial to Wishbone bridge
        # ----------------------------
        self.add_cpu(uart.UARTWishboneBridge(
            self.platform.request("serial"),
            self.clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # Clock Reset Generation
        self.submodules.crg = SP605_CRG(self.platform, self.clk_freq)

        # FPGA identification
        self.submodules.dna = dna.DNA()

        # ----------------------------
        #  FMC LPC connectivity & LTC LVDS driver
        # ----------------------------
        self.platform.add_extension(LTCPhy.pads)
        # LTCPhy drives `sample` clock domain
        self.submodules.lvds = LTCPhy(self.platform, 120e6)

        # ----------------------------
        #  SPI master
        # ----------------------------
        spi_pads = self.platform.request("LTC_SPI")
        self.submodules.spi = spi.SPIMaster(spi_pads)

        # ----------------------------
        #  Acquisition memory for ADC data
        # ----------------------------
        mem = Memory(16, 4096)
        self.specials += mem
        self.submodules.sample_ram = SRAM(mem, read_only=True)
        self.register_mem("sample", 0x50000000, self.sample_ram.bus, 4096)
        self.submodules.acq = Acquisition(mem)
        self.specials += MultiReg(
            self.platform.request("user_btn"), self.acq.trigger
        )
        self.comb += [
            self.platform.request("user_led").eq(self.acq.busy),
            self.acq.data_in.eq(self.lvds.sample_out),
        ]

        # ----------------------------
        #  Provide a 114 MHz ENC clock signal on SMA_GPIO
        # ----------------------------
        enc_out = Signal()
        self.specials += Instance(
            "ODDR2",
            o_Q=enc_out,
            i_C0=ClockSignal("clk_114"),
            i_C1=~ClockSignal("clk_114"),
            i_CE=1,
            i_D0=1,
            i_D1=0
        )
        gpio_pads = self.platform.request("ENC_CLK")
        self.specials += DifferentialOutput(enc_out, gpio_pads.p, gpio_pads.n)


# Add etherbone support
class HelloLtcEth(HelloLtc):
    csr_map_update(SoCCore.csr_map, ["ethphy"])

    def __init__(self, **kwargs):
        HelloLtc.__init__(self, **kwargs)
        # ethernet PHY and UDP/IP stack
        mac_address = 0x01E625688D7C
        ip_address = "192.168.1.50"
        self.submodules.ethphy = LiteEthPHY(
            self.platform.request("eth_clocks"),
            self.platform.request("eth"),
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
    # clk_freq should be > 125 MHz for ethernet !!!
    soc = HelloLtcEth(platform=sp605.Platform(), clk_freq=int(150e6))
    main(soc, doc=__doc__)
