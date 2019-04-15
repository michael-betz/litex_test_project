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
from litex.soc.cores.frequency_meter import FrequencyMeter
from liteeth.phy import LiteEthPHY
from liteeth.core import LiteEthUDPIPCore
from liteeth.common import convert_ip
from liteeth.core.mac import LiteEthMAC
from liteeth.frontend.etherbone import LiteEthEtherbone
from sys import argv, exit, path
from shutil import copyfile
path.append("../sp605")
path.append("../sp605/iserdes")
from sp605_crg import SP605_CRG
from iserdes.ltc_phy import LedBlinker


# create our bare bones soc (no cpu, only wishbone 2 serial)
class BaseSoc(SoCCore):
    csr_map_update(SoCCore.csr_map, ["dna"])

    def __init__(self, **kwargs):
        self.platform = sp605.Platform()
        SoCCore.__init__(
            # cd_sys should be > 125 MHz for ethernet !!!
            self, self.platform, int(125e6),
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
            self.clk_freq,
            baudrate=1152000
        ))
        self.add_wb_master(self.cpu.wishbone)

        # Clock Reset Generation
        self.submodules.crg = SP605_CRG(self.platform, self.clk_freq)

        # FPGA identification
        self.submodules.dna = dna.DNA()


# Add ethernet support
class HelloETH(BaseSoc):
    csr_map_update(SoCCore.csr_map, ["ethphy"])  #, "ethmac"])
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
            self.clk_freq,
            # avoid huge reset delay in simulation
            with_hw_init_reset="synth" in argv
        )
        self.submodules.core = LiteEthUDPIPCore(
            self.ethphy, mac_address, convert_ip(ip_address), self.clk_freq
        )

        # MAC = wishbone slave = to let the CPU talk over ethernet
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

        # Etherbone = wishbone master = read and write registers remotely
        self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 1234, mode="master")
        self.add_wb_master(self.etherbone.wishbone.bus)


class HelloETH_dbg(HelloETH):
    csr_map_update(SoCCore.csr_map, ["analyzer", "f_tx"])

    def __init__(self, **kwargs):
        from litescope import LiteScopeAnalyzer
        HelloETH.__init__(self, **kwargs)
        p = self.platform
        self.submodules.blink_rx = ClockDomainsRenamer("eth_rx")(LedBlinker(125e6))
        self.submodules.blink_tx = ClockDomainsRenamer("eth_tx")(LedBlinker(125e6))
        self.submodules.f_tx = FrequencyMeter(int(100e6))
        self.comb += [
            p.request("user_led").eq(self.blink_rx.out),
            p.request("user_led").eq(self.blink_tx.out),
            self.f_tx.clk.eq(ClockSignal("eth_tx"))
        ]

        debug = [
            p.lookup_request("eth").tx_en,
            p.lookup_request("eth").tx_er,
            p.lookup_request("eth").tx_data,
            p.lookup_request("eth").mdc,

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
            self.core.ip.crossbar.master.sink.protocol
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(debug, 4096)

    def do_exit(self, vns):
        self.analyzer.export_csv(vns, "build/analyzer.csv")


if __name__ == '__main__':
    if len(argv) < 2:
        print(__doc__)
        exit(-1)
    tName = argv[0].replace(".py", "")
    # soc = BaseSoc()
    soc = HelloETH()
    # soc = HelloETH_dbg()
    vns = None
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(
            build_name=tName, regular_comb=False, blocking_assign=True
        )
        copyfile("./build/gateware/mem_1.init", "mem_1.init")
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
