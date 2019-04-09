"""
first attempt to get the ethernet
running on the sp605

try:
 python3 hello_ETH.py <build / synth / config>
"""
from migen import *
from litex.boards.platforms import sp605
from litex.build.generic_platform import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import dna, uart
from liteeth.phy import LiteEthPHY
from liteeth.core import LiteEthUDPIPCore
from liteeth.common import convert_ip
# from liteeth.core.mac import LiteEthMAC
from sys import argv, exit, path
from shutil import copyfile
path.append("../sp605")
path.append("../sp605/iserdes")
from sp605_crg import SP605_CRG


# create our bare bones soc (no cpu, only wishbone 2 serial)
class BaseSoc(SoCCore):
    csr_map = {
        "dna": 10
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, **kwargs):
        self.platform = sp605.Platform()
        self.sys_clk_freq = int(100e6)  # 100 MHz, 10 ns
        SoCCore.__init__(
            self, self.platform, self.sys_clk_freq,
            cpu_type=None,
            csr_data_width=32,
            with_uart=False,
            with_timer=False,
            integrated_rom_size=0,
            integrated_main_ram_size=0,
            # integrated_sram_size=0,
            ident="SP605 eth demo", ident_version=True,
            **kwargs
        )

        # Serial to Wishbone bridge
        self.add_cpu(uart.UARTWishboneBridge(
            self.platform.request("serial"),
            self.sys_clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # Clock Reset Generation
        self.submodules.crg = SP605_CRG(self.platform, self.sys_clk_freq)

        # FPGA identification
        self.submodules.dna = dna.DNA()


# Add ethernet support
class HelloETH(BaseSoc):
    csr_map = {"ethphy": 20} #, "ethmac": 21}
    csr_map.update(BaseSoc.csr_map)
    # interrupt_map = {"ethmac": 3}
    # interrupt_map.update(BaseSoc.interrupt_map)
    # mem_map = {"ethmac": 0x30000000}  # (shadow @0xb0000000)
    # mem_map.update(BaseSoc.mem_map)

    def __init__(self, **kwargs):
        BaseSoc.__init__(self, **kwargs)

        # ethernet PHY and UDP/IP stack
        mac_address = 0x10e2d5001000
        ip_address = "192.168.1.50"
        self.submodules.ethphy = LiteEthPHY(
            self.platform.request("eth_clocks"),
            self.platform.request("eth"),
            self.clk_freq
        )
        self.submodules.core = LiteEthUDPIPCore(
            self.ethphy, mac_address, convert_ip(ip_address), self.clk_freq
        )

        # self.submodules.ethmac = LiteEthMAC(
        #     phy=self.ethphy, dw=32, interface="wishbone",
        #     endianness="little", with_preamble_crc=False
        # )
        # self.add_wb_slave(
        #     mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus
        # )
        # self.add_memory_region(
        #     "ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000
        # )


class HelloETH_dbg(HelloETH):
    csr_map = {"analyzer": 30}
    csr_map.update(HelloETH.csr_map)

    def __init__(self, **kwargs):
        from litescope import LiteScopeAnalyzer
        HelloETH.__init__(self, **kwargs)

        self.core_icmp_rx_fsm_state = Signal(4)
        self.core_icmp_tx_fsm_state = Signal(4)
        self.core_udp_rx_fsm_state = Signal(4)
        self.core_udp_tx_fsm_state = Signal(4)
        self.core_ip_rx_fsm_state = Signal(4)
        self.core_ip_tx_fsm_state = Signal(4)
        self.core_arp_rx_fsm_state = Signal(4)
        self.core_arp_tx_fsm_state = Signal(4)
        self.core_arp_table_fsm_state = Signal(4)

        debug = [
            # MAC interface
            self.core.mac.core.sink.valid,
            self.core.mac.core.sink.last,
            self.core.mac.core.sink.ready,
            self.core.mac.core.sink.data,

            self.core.mac.core.source.valid,
            self.core.mac.core.source.last,
            self.core.mac.core.source.ready,
            self.core.mac.core.source.data,

            # ICMP interface
            self.core.icmp.echo.sink.valid,
            self.core.icmp.echo.sink.last,
            self.core.icmp.echo.sink.ready,
            self.core.icmp.echo.sink.data,

            self.core.icmp.echo.source.valid,
            self.core.icmp.echo.source.last,
            self.core.icmp.echo.source.ready,
            self.core.icmp.echo.source.data,

            # IP interface
            self.core.ip.crossbar.master.sink.valid,
            self.core.ip.crossbar.master.sink.last,
            self.core.ip.crossbar.master.sink.ready,
            self.core.ip.crossbar.master.sink.data,
            self.core.ip.crossbar.master.sink.ip_address,
            self.core.ip.crossbar.master.sink.protocol,

            # State machines
            self.core_icmp_rx_fsm_state,
            self.core_icmp_tx_fsm_state,

            self.core_arp_rx_fsm_state,
            self.core_arp_tx_fsm_state,
            self.core_arp_table_fsm_state,

            self.core_ip_rx_fsm_state,
            self.core_ip_tx_fsm_state,

            self.core_udp_rx_fsm_state,
            self.core_udp_tx_fsm_state
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(debug, 4096)

    def do_finalize(self):
        HelloETH.do_finalize(self)
        self.comb += [
            self.core_icmp_rx_fsm_state.eq(self.core.icmp.rx.fsm.state),
            self.core_icmp_tx_fsm_state.eq(self.core.icmp.tx.fsm.state),

            self.core_arp_rx_fsm_state.eq(self.core.arp.rx.fsm.state),
            self.core_arp_tx_fsm_state.eq(self.core.arp.tx.fsm.state),
            self.core_arp_table_fsm_state.eq(self.core.arp.table.fsm.state),

            self.core_ip_rx_fsm_state.eq(self.core.ip.rx.fsm.state),
            self.core_ip_tx_fsm_state.eq(self.core.ip.tx.fsm.state),

            self.core_udp_rx_fsm_state.eq(self.core.udp.rx.fsm.state),
            self.core_udp_tx_fsm_state.eq(self.core.udp.tx.fsm.state)
        ]

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "build/analyzer.csv")


if __name__ == '__main__':
    if len(argv) < 2:
        print(__doc__)
        exit(-1)
    tName = argv[0].replace(".py", "")
    soc = HelloETH_dbg()
    vns = None
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(build_name=tName)
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=True, compile_software=True
        )
        vns = builder.build(build_name=tName)
    if "config" in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
    print(vns)
    try:
        soc.do_exit(vns)
    except:
        pass
