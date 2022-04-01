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
from phy_10g import Phy10G
from litex.soc.interconnect.csr import CSRStorage, AutoCSR
from liteeth.common import stream, eth_udp_user_description


class UdpSender(Module, AutoCSR):
    def __init__(self, D, dst_ip="192.168.1.100"):
        '''
        D must be >= phy datapath width

        send UDP packets with content
          08 07 06 05 04 03 02 01           for n_words - 1 times
          64 bit sequence number
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

        self.fsm.act("IDLE",
            NextValue(timer, timer + 1),
            If((self.period.storage > 0) & (timer >= self.period.storage),
                NextValue(timer, 0),
                NextState("SEND")
            )
        )
        fsm.act("SEND",
            source.valid.eq(1),
            source.src_port.eq(self.dst_port.storage),
            source.dst_port.eq(self.dst_port.storage),
            source.ip_address.eq(self.dst_ip.storage),
            source.length.eq(self.n_words.storage * D),  # payload length
            If(cur_word == 1,
                source.data.eq(seq),
            ).Else(
                source.data.eq(0x0807060504030201)
            ),
            If(cur_word >= self.n_words.storage,
                source.last.eq(1),
                # last_be indicates that this byte is the first one
                # which is no longer valid
                # if all bytes are valid in the last cycle,
                # set last=1 and last_be=0
                source.last_be.eq(0x80),
                If(source.ready,
                    NextValue(cur_word, 1),
                    NextValue(seq, seq + 1),
                    NextState("IDLE"),
                ),
            ).Else(
                If(source.ready,
                    NextValue(cur_word, cur_word + 1)
                )
            ),
        )


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

        my_ip = "192.168.10.50"
        my_mac = 0x10e2d5000000

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
        self.submodules.udp_sender = UdpSender(D=D, dst_ip="192.168.10.1")
        self.comb += [
            self.udp_sender.source.connect(self.udpp.sink),
            self.udpp.source.ready.eq(1)
        ]

        # ----------------------
        #  Etherbone
        # ----------------------
        # Needs more work to be compatible with 64 bit wide datapath


class DevSoC(TestSoc):
    def __init__(self, **kwargs):
        from litescope import LiteScopeAnalyzer
        super().__init__(**kwargs)
        analyzer_signals = [
            self.udpp.sink.valid,
            self.udpp.sink.ready,
            self.udpp.sink.last,
            self.udpp.sink.data,
            # self.xgmii.rx_ctl,
            # self.xgmii.rx_data,
            # self.xgmii.tx_ctl,
            # self.xgmii.tx_data,
            # self.xgmii.pma_status,
            # self.xgmii.tx_disable,
            # self.xgmii.qplllock  ,
            # self.xgmii.gtrxreset ,
            # self.xgmii.gttxreset ,
            # self.xgmii.txusrrdy  ,
            # self.xgmii.pcs_clear  ,
            # self.xgmii.pma_multi  ,
            self.ethphy.rx.source.valid,
            self.ethphy.rx.source.data,
            self.ethphy.tx.sink.valid,
            self.ethphy.tx.sink.data,
            # self.teng_udp_core.mac.core.sink.valid,
            # self.teng_udp_core.mac.core.sink.data,
            # self.teng_udp_core.arp.rx.sink.valid,
            # self.teng_udp_core.arp.rx.sink.data,
            # self.teng_udp_core.arp.tx.source.valid,
            # self.teng_udp_core.arp.tx.source.data,
        ]
        self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 4096,
                                                     clock_domain="eth_tx",
                                                     csr_csv="analyzer.csv")
        self.add_csr("analyzer")



# -------------------
#  Testbench
# -------------------
from litex.soc.interconnect.stream_sim import *
from litex.gen.sim import *
from liteeth.core import LiteEthUDPIPCore
import sys
sys.path.append('/home/michael/fpga_wsp/hello_petsys/')
from model import phy, mac, arp, ip, icmp, dumps

local_ip = convert_ip('192.168.1.9')
local_mac = 0x001000000100

dst_ip = convert_ip('192.168.1.10')
dst_mac = 0x012345654321

class DUT(Module):
    def __init__(self):
        D = 8  # Datapath width [bytes]

        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.eth_tx = ClockDomain()
        self.clock_domains.eth_rx = ClockDomain()

        self.clk_freq = 100000
        self.submodules.ethphy = phy.PHY(D * 8, debug=True)
        self.submodules.mac_model = mac.MAC(self.ethphy, debug=True, loopback=False)
        self.submodules.arp_model = arp.ARP(self.mac_model, dst_mac, dst_ip, debug=True)
        self.submodules.ip_model = ip.IP(self.mac_model, dst_mac, dst_ip, debug=True, loopback=False)
        self.submodules.icmp_model = icmp.ICMP(self.ip_model, dst_ip, debug=True)

        ethcore = LiteEthUDPIPCore(
            phy=self.ethphy,
            mac_address=local_mac,
            ip_address=local_ip,
            clk_freq=self.clk_freq,
            dw=self.ethphy.dw
        )
        self.submodules.ethcore = ethcore

        # ----------------------
        #  UDP packet sender
        # ----------------------
        self.udpp = self.ethcore.udp.crossbar.get_port(1337, D * 8)
        self.submodules.udp_sender = UdpSender(D=D, dst_ip="192.168.1.10")
        self.comb += [
            self.udp_sender.source.connect(self.udpp.sink),
            self.udpp.source.ready.eq(1)
        ]


def fire_ping_request(dut):
    packet = mac.MACPacket(dumps.ping_request)
    packet.decode_remove_header()
    packet = ip.IPPacket(packet)
    packet.decode()
    packet = icmp.ICMPPacket(packet)
    packet.decode()
    dut.icmp_model.send(packet)


def main_generator(dut):
    '''
    We will see an ARP request to fetch the MAC belonging to dst_ip
    Then we should see UDP packets
    '''
    yield (dut.udp_sender.period.storage.eq(0))

    # print("---------- Ping request ----------")
    fire_ping_request(dut)

    for i in range(512):
        yield



def main():
    if 'sim' in argv:
        dut = DUT()
        generators = {
            "sys" :   [main_generator(dut)],
            "eth_tx": [dut.ethphy.phy_sink.generator(),
                       dut.ethphy.generator()],
            "eth_rx":  dut.ethphy.phy_source.generator()
        }
        clocks = {
            "sys":    10,
            "eth_rx": 10,
            "eth_tx": 10
        }
        run_simulation(dut, generators, clocks, vcd_name="udp_sender.vcd")
        return

    soc = DevSoC()
    soc.platform.name = 'hello_10G'
    builder = Builder(
        soc,
        compile_gateware='synth' in argv,
        csr_csv='./build/csr.csv',
        csr_json='./build/csr.json',
    )
    if ('build' in argv) or ('synth' in argv):
        vns = builder.build()
        soc.analyzer.do_exit(vns)

    if 'load' in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(join(
            builder.gateware_dir,
            soc.platform.name + ".bit"
        ))


if __name__ == "__main__":
    main()
