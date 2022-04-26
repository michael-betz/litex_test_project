'''
Demonstrate forwarding a data stream over UDP on 10GbE

# Set the host PCs IP address
ip addr add dev enp3s0f0 192.168.1.50/24

# Set maximum UDP sending rate to 125k packets / s (already the default)
litex_server --uart --uart-port /dev/ttyUSB1 --uart-baudrate 1152000
litex_cli --write 0x00002800 1000

# Show received UDP packet stream
netcat -lup 1337 | hexdump -C

# Add flood-ping stress test
sudo ping -f 192.168.1.50
'''
from sys import argv
from os.path import join

from migen import *
from litex.soc.integration.builder import Builder
from litex_boards.targets.berkeleylab_marble import BaseSoC
from liteeth.core import LiteEthUDPIPCore
from liteeth.common import convert_ip
from liteeth.frontend.etherbone import LiteEthEtherbone
from phy_10g import Phy10G
from litex.soc.interconnect.csr import CSRStorage, AutoCSR
from litex.soc.interconnect import wishbone
from liteeth.common import stream, eth_udp_user_description, icmp_type_ping_request
from litescope import LiteScopeAnalyzer


class UdpSender(Module, AutoCSR):
    def __init__(self, D, dst_ip="192.168.1.100"):
        '''
        D must be >= phy datapath width

        send UDP packets which can be verified by udprc.c
        each packet consists of N 8-byte words
        the first word is the key and increments with each packet
        each word is calculated as (sta ^ word_id)
        where sta is initialized with key
        and incremented by sta = 3 * sta + 1 for every word
        '''
        self.source = source = stream.Endpoint(eth_udp_user_description(D * 8))

        ###

        seq = Signal(64)
        timer = Signal(32)
        cur_word = Signal(16, reset=1)
        self.period = CSRStorage(32, reset=0x1FFFFFFF)
        self.dst_ip = CSRStorage(
            32,
            reset=convert_ip(dst_ip),
            description='Destination IP address for UDP stream'
        )
        self.dst_port = CSRStorage(
            16,
            reset=1337,
            description='Destination port number'
        )
        self.n_words = CSRStorage(
            16,
            reset=4,
            description='Number of D-bit words in the paket'
        )

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        key = Signal(64)
        sta = Signal(64)

        self.fsm.act("IDLE",
            NextValue(timer, timer + 1),
            If((self.period.storage > 0) & (timer >= self.period.storage),
                NextValue(timer, 0),
                NextValue(sta, key),
                NextState("SEND")
            )
        )
        fsm.act("SEND",
            source.valid.eq(1),
            source.src_port.eq(self.dst_port.storage),
            source.dst_port.eq(self.dst_port.storage),
            source.ip_address.eq(self.dst_ip.storage),
            source.length.eq(self.n_words.storage * D),  # payload length
            source.data.eq(sta ^ (cur_word - 1)),
            If(cur_word >= self.n_words.storage,
                source.last.eq(1),
                # last_be marks the last valid byte
                # 0b10000000 = 0x80 indicates all 8 bytes are valid
                source.last_be.eq(0x80),
                If(source.ready,
                    NextValue(cur_word, 1),
                    NextValue(key, key + 1),
                    NextState("IDLE"),
                ),
            ).Else(
                If(source.ready,
                    NextValue(cur_word, cur_word + 1),
                    NextValue(sta, sta * 3 + 1)
                )
            ),
        )


my_ip = "192.168.10.50"
my_mac = 0x10e2d5000000
dst_ip = "192.168.10.1"


class TestSoc(BaseSoC):
    def __init__(self):
        ''' for testing on the berkeleylab_marble target. Ping-able. '''
        BaseSoC.__init__(
            self,
            cpu_type=None,
            # f_sys must be >= 156.25 MHz
            sys_clk_freq=int(166.67e6),
            integrated_main_ram_size=8,
            integrated_sram_size=0,
            with_timer=False,
            with_etherbone=False,
            uart_name='uartbone',
            uart_baudrate=1152000  # not a typo
        )

        self.submodules.ethphy = Phy10G(
            self.platform,
            self.platform.request("qsfp", 1),
            self.platform.request("clkmgt", 1),  # SI570_CLK
            self.sys_clk_freq
        )
        self.ethphy.add_csr()

        # TODO this overrides the constraint from the IP file and causes a
        # critical warning. But without it Vivado fails to apply the false_path
        # constraint below.
        # https://support.xilinx.com/s/article/55248?language=en_US
        self.platform.add_period_constraint(
            self.ethphy.coreclk_out,
            1e9 / 156.25e6
        )
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.coreclk_out
        )

        # ----------------------
        #  UDP stack
        # ----------------------
        ethcore = LiteEthUDPIPCore(
            phy=self.ethphy,
            mac_address=my_mac,
            ip_address=my_ip,
            clk_freq=self.clk_freq,
            dw=self.ethphy.dw
        )
        self.submodules.ethcore = ethcore

        # ----------------------
        #  UDP packet sender
        # ----------------------
        D = 8  # Datapath width [bytes]
        self.udpp = self.ethcore.udp.crossbar.get_port(1337, D * 8)
        self.submodules.udp_sender = UdpSender(D=D, dst_ip=dst_ip)
        self.comb += [
            self.udp_sender.source.connect(self.udpp.sink),
            self.udpp.source.ready.eq(1)
        ]

        # ----------------------
        #  Etherbone
        # ----------------------
        # Needs more work to be compatible with 64 bit wide datapath
        self.submodules.etherbone = LiteEthEtherbone(
            self.ethcore.udp,
            1234,
            buffer_depth=8
        )
        self.bus.add_master(master=self.etherbone.wishbone.bus)
        # self.submodules.sram = wishbone.SRAM(1024)
        # self.comb += self.etherbone.wishbone.bus.connect(self.sram.bus)

        # ----------------------
        #  Analyzer
        # ----------------------
        # analyzer_signals = [
        #     self.sram.bus,
        #     self.etherbone.packet.source
        # ]
        # self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
        #     depth        = 512,
        #     clock_domain = "sys",
        #     samplerate   = self.sys_clk_freq,
        #     csr_csv      = "analyzer.csv"
        # )
        # self.add_csr("analyzer")


# -------------------
#  Testbench
# -------------------
from litex.soc.interconnect.stream_sim import *
from litex.gen.sim import *
# Need to add liteeth directory to PYTHONPATH
from test.model import phy, mac, arp, ip, icmp, dumps


class DUT0(Module):
    def __init__(self, D):
        ''' D = Datapath width [bytes] '''
        self.submodules.udp_sender = UdpSender(D=D, dst_ip=dst_ip)
        self.comb += [
            self.udp_sender.source.ready.eq(1)
        ]


class DUT1(DUT0):
    def __init__(self, D):
        super().__init__(D)

        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.eth_tx = ClockDomain()
        self.clock_domains.eth_rx = ClockDomain()

        self.clk_freq = 100000
        dst_ip_ = convert_ip(dst_ip)
        dst_mac = my_mac + 32
        self.submodules.ethphy = phy.PHY(D * 8, debug=True, pcap_file='dump.pcap')
        self.submodules.mac_model = mac.MAC(self.ethphy, debug=True, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, dst_mac, dst_ip_, debug=True)
        self.submodules.ip_model = ip.IP(self.mac_model, dst_mac, dst_ip_, debug=True, loopback=False)
        self.submodules.icmp_model = icmp.ICMP(self.ip_model, dst_ip_, debug=True)

        ethcore = LiteEthUDPIPCore(
            phy=self.ethphy,
            mac_address=my_mac,
            ip_address=convert_ip(my_ip),
            clk_freq=self.clk_freq,
            dw=self.ethphy.dw
        )
        self.submodules.ethcore = ethcore

        # ----------------------
        #  UDP packet sender
        # ----------------------
        self.udpp = self.ethcore.udp.crossbar.get_port(1337, D * 8)
        self.comb += [
            self.udp_sender.source.connect(self.udpp.sink),
        ]


def send_icmp(dut, msgtype=icmp_type_ping_request, code=0):
    p = icmp.ICMPPacket(b"Hello World 123456")
    p.code = code
    p.checksum = 0
    p.msgtype = msgtype
    p.ident = 0x69b3
    p.sequence = 0x1
    dut.icmp_model.send(p, target_ip=convert_ip(my_ip))


def main():
    D = 8

    if 'sim0' in argv:
        # ---------------------------------------
        #  look at the UdpSender output stream
        # ---------------------------------------
        dut = DUT0(D)

        def generator0(dut):
            yield (dut.udp_sender.period.storage.eq(3))
            for i in range(64):
                yield
        run_simulation(dut, generator0(dut), vcd_name="udp_sender.vcd")
        return

    if 'sim1' in argv:
        # ---------------------------------------
        #  look at the liteeth UDP packets
        # ---------------------------------------
        dut = DUT1(D)

        def generator1(dut):
            # We will see an ARP request to fetch the MAC belonging to dst_ip
            # Then we should see UDP packets
            yield (dut.udp_sender.period.storage.eq(100))
            send_icmp(dut)
            for i in range(512):
                yield
        generators = {
            "sys" :   [generator1(dut)],
            "eth_tx": [dut.ethphy.phy_sink.generator(),
                       dut.ethphy.generator()],
            "eth_rx":  dut.ethphy.phy_source.generator()
        }
        clocks = {
            "sys":    10,
            "eth_rx": 9,
            "eth_tx": 8
        }
        run_simulation(dut, generators, clocks, vcd_name="udp_sender.vcd")
        return

    # ---------------------------------------
    #  synthesize for Marble board / load
    # ---------------------------------------
    soc = TestSoc()
    # soc = DevSoc()
    soc.platform.name = 'hello_10G'
    builder = Builder(
        soc,
        compile_gateware='synth' in argv,
        csr_csv='./build/csr.csv',
        csr_json='./build/csr.json',
    )
    if ('build' in argv) or ('synth' in argv):
        vns = builder.build()
        # soc.analyzer.do_exit(vns)

    if 'load' in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(join(
            builder.gateware_dir,
            soc.platform.name + ".bit"
        ))


if __name__ == "__main__":
    main()
