# Demo 10 Gigabit ethernet on Marble board
#
# Needs updated Marble platform file:
# cd ../xdc
# python gen_marble.py Marble.xdc > <...>/litex/litex-boards/litex_boards/platforms/berkeleylab_marble.py
#
# # TODO:
# * QSFP+ control lines:
#   * ModSelL=0 to enable I2C interface
#   * LPMode=0 to disable low power mode (ignored?)
#   * ModPrsL reads 0 when QSFP module is inserted
#   * IntL reads 0 on fault / critical status (to be read over I2C then)
# * Add IBERT IP for GTX diagnostics over JTAG
# * Fix timing constraint Critical Warnings (broken in litex?)
# * don't always re-generate the IP
#
#
# # Clocking
# Options to get the 156.25 MHz transceiver clock on Marble:
# 1. Modify CDCM61004RHBT configuration
#   * strapping pins: PR0 PR1  OD0 OD1 OD2  OS1 OS0, internal pullup!
#   * 0R resistors:   R96 R97  R98 R99 R100 R101 R102
#   * default is: 4 20 4, 11 110 11, 125.00 MHz
#   * modified:   3 25 4, 01 110 11, 156.25 MHz
#   * Modification: add 0R resistor to R96
#   * Will loose 125 MHz clock (maybe needed for GbE)
# 2. Program the Si570 over I2C
#   * I2C_APP bus, port 6 of multiplexer
#   * No HW modification needed
#   * By default routed on ADN4600ACPZ: Si570, INP3 --> OP1, MGT_CLK_1
#   * Use modified MMC firmware to init Si570 on powerup:
#     https://github.com/yetifrisstlama/Marble-MMC/tree/si570

import sys
sys.path.append('/home/michael/fpga_wsp/hello_petsys')
from test_soc_eth_min import UdpSender

from sys import argv
from os.path import join
from migen import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder
from litex_boards.targets.berkeleylab_marble import BaseSoC
from litex.soc.cores.freqmeter import FreqMeter
from liteeth.phy.xgmii import LiteEthPHYXGMIITX, LiteEthPHYXGMIIRX
from liteeth.core import LiteEthIPCore, LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone
# from litescope import LiteScopeAnalyzer


def add_ip(platform, name, module_name, config={}, synth=True):
    ''' add a Vivado IP core to the design '''
    ip_tcl = [
        f"create_ip -name {name} -vendor xilinx.com -library ip -version 6.0 -module_name {module_name}",
        "set_property -dict [list \\",
    ]
    for k, v in config.items():
        ip_tcl.append("    CONFIG.{} {} \\".format(k, '{{' + str(v) + '}}'))
    ip_tcl.append(f"] [get_ips {module_name}]")
    if synth:
        # ip_tcl.append(f"generate_target all [get_ips {module_name}]")
        ip_tcl.append(f"synth_ip [get_ips]")
    platform.toolchain.pre_synthesis_commands += ip_tcl


class Phy10G(Module, AutoCSR):
    def __init__(self, platform, qsfp_pads, refclk_pads, sys_clk_freq):
        '''
        10 Gigabit ethernet PHY, using the Xilinx PCS/PMA IP core

        self.sink, self.source: xgmii interface to MAC
        qsfp_pads.{tx/rx}_{p/n}: pads of the SFP+ transceiver module
        refclk_pads.{p/n}: pads of a decent 156.25 MHz clock source
        '''
        ###

        self.dw = 64
        self.platform = platform
        self.tx_clk_freq = self.rx_clk_freq = 156.25e6
        self.sys_clk_freq = sys_clk_freq

        add_ip(
            platform,
            "ten_gig_eth_pcs_pma",
            "pcs_pma",
            {
                "MDIO_Management": False,
                "SupportLevel": 1,
                "baser32": "64bit",
                "refclkrate": self.tx_clk_freq / 1e6,
                "DClkRate": self.sys_clk_freq / 1e6,
                "SupportLevel": 1  # Add shared logic to core
            }
        )

        self.coreclk_out = Signal()
        areset_datapathclk_out = Signal()
        self.core_status = Signal()

        # TODO: attach config / status word to CSR bus
        self.configuration_vector = Signal(536)
        self.status_vector = Signal(448)

        # TODO: make sure DRP is accessible by JTAG or attach to wishbone
        drp_gnt = Signal()
        drp_den_i = Signal()
        drp_dwe_i = Signal()
        drp_daddr_i = Signal(16)
        drp_di_i = Signal(16)
        drp_drdy_i = Signal()
        drp_drpdo_i = Signal(16)
        drp_req = Signal()
        drp_den_o = Signal()
        drp_dwe_o = Signal()
        drp_daddr_o = Signal(16)
        drp_di_o = Signal(16)
        drp_drdy_o = Signal()
        drp_drpdo_o = Signal(16)

        self.pads = Record([
            ('tx_data', 64),
            ('tx_ctl', 8),
            ('rx_data', 64),
            ('rx_ctl', 8),
        ])

        self.specials.pcs_pma = Instance(
            "pcs_pma",
            i_xgmii_txd=self.pads.tx_data,
            i_xgmii_txc=self.pads.tx_ctl,
            o_xgmii_rxd=self.pads.rx_data,
            o_xgmii_rxc=self.pads.rx_ctl,

            # 156.25 MHz transceiver clock / reset
            i_refclk_p=refclk_pads.p,
            i_refclk_n=refclk_pads.n,
            i_reset=ResetSignal(),  # Asynchronous Master Reset
            # create_waiver -type CDC -id CDC-11 -from [get_pins FDPE_1/C]  -to [get_pins {pcs_pma/inst/ten_gig_eth_pcs_pma_block_i/pcs_pma_local_clock_reset_block/coreclk_areset_sync_i/sync1_r_reg[0]/PRE}]
            # create_waiver -type CDC -id CDC-11 -from [get_pins FDPE_1/C]  -to [get_pins {pcs_pma/inst/ten_gig_eth_pcs_pma_shared_clock_reset_block/areset_coreclk_sync_i/sync1_r_reg[0]/PRE}]
            o_coreclk_out=self.coreclk_out,  # clock for the TX-datapath
            # reset signal sync. to coreclk_out
            o_areset_datapathclk_out=areset_datapathclk_out,

            # SFP+ SERDES lane
            o_txp=qsfp_pads.tx_p,
            o_txn=qsfp_pads.tx_n,
            i_rxp=qsfp_pads.rx_p,
            i_rxn=qsfp_pads.rx_n,
            i_sim_speedup_control=0,

            # SFP+ transceiver status pins
            i_signal_detect=1,
            i_tx_fault=0,
            # o_tx_disable=

            # MDIO configuration / status word
            i_configuration_vector=self.configuration_vector,
            o_status_vector=self.status_vector,
            o_core_status=self.core_status,  # Bit 0 = PCS Block Lock, Bits [7:1] are reserved

            # DRP port
            i_dclk=ClockSignal(),
            i_drp_gnt=drp_gnt,
            i_drp_den_i=drp_den_i,
            i_drp_dwe_i=drp_dwe_i,
            i_drp_daddr_i=drp_daddr_i,
            i_drp_di_i=drp_di_i,
            i_drp_drdy_i=drp_drdy_i,
            i_drp_drpdo_i=drp_drpdo_i,
            o_drp_req=drp_req,
            o_drp_den_o=drp_den_o,
            o_drp_dwe_o=drp_dwe_o,
            o_drp_daddr_o=drp_daddr_o,
            o_drp_di_o=drp_di_o,
            o_drp_drdy_o=drp_drdy_o,
            o_drp_drpdo_o=drp_drpdo_o,

            # 0b111 = 10GBASE-SR, 0b110= 10GBASE-LR, 0b101 = 10GBASE-ER
            i_pma_pmd_type=0b111,
        )

        # Create clock-domains
        self.clock_domains.cd_eth = ClockDomain()
        self.comb += [
            self.cd_eth.clk.eq(self.coreclk_out),
            # self.cd_eth_tx.clk.eq(self.coreclk_out),
            self.cd_eth.rst.eq(areset_datapathclk_out),
            # self.cd_eth_tx.rst.eq(areset_datapathclk_out)
        ]

        self.comb += [
            # If no arbitration is required on the GT DRP ports then connect
            # REQ to GNT and connect other signals i <= o;
            drp_gnt.eq(drp_req),
            drp_den_i.eq(drp_den_o),
            drp_dwe_i.eq(drp_dwe_o),
            drp_daddr_i.eq(drp_daddr_o),
            drp_di_i.eq(drp_di_o),
            drp_drdy_i.eq(drp_drdy_o),
            drp_drpdo_i.eq(drp_drpdo_o)
        ]

        # Litex PHY
        self.submodules.tx = ClockDomainsRenamer('eth')(
            # dic: deficit idle count
            LiteEthPHYXGMIITX(self.pads, self.dw, dic=True)
        )
        self.submodules.rx = ClockDomainsRenamer('eth')(
            LiteEthPHYXGMIIRX(self.pads, self.dw)
        )
        self.sink, self.source = self.tx.sink, self.rx.source

    def add_csr(self):
        # Add frequency-meter to 156.25 MHz reference clock
        self.submodules.f_coreclk = FreqMeter(
            period=int(self.sys_clk_freq),
            width=4,
            clk=ClockSignal('eth_tx')
        )

        # Config / Status CSRs
        self.status = CSRStatus(len(self.status_vector))
        # 536 bit config reg is very challenging for the synthesizer
        # self.configuration = CSRStorage(len(self.configuration_vector))
        self.comb += [
            self.status.status.eq(self.status_vector),
            # self.configuration_vector.eq(self.configuration.storage)
        ]

    # def add_ibert(self):
        # in-system IBERT only supported on Ultrascale devices :(


class TestSoc(BaseSoC):
    def __init__(self):
        ''' for testing on the berkeleylab_marble target. Ping-able. '''
        BaseSoC.__init__(
            self,
            cpu_type=None,
            # 100 MHz seems to break timing, why??????
            # TODO look at CDC -.-
            sys_clk_freq=int(166e6),
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
        # self.ethphy.add_csr()

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

        # This violates timing by 3 ns
        # and sends a ping response only every 3rd packet :p
        # self.add_etherbone(
        #     phy=self.ethphy,
        #     mac_address=my_mac,
        #     ip_address=my_ip,
        #     buffer_depth=32,
        #     udp_port=1234,
        #     with_timing_constraints=True
        # )

        # ----------------------
        #  UDP stack
        # ----------------------
        # This meets timing (f_sys = 125 MHz) and pings fine. But no UDP :(
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
        udpp = self.ethcore.udp.crossbar.get_port(1337, D * 8)
        self.submodules.udp_sender = UdpSender(D=D, dst_ip="192.168.10.1")
        self.comb += [
            self.udp_sender.source.connect(udpp.sink),
            udpp.source.ready.eq(1)
        ]

        # ----------------------
        #  Etherbone
        # ----------------------
        # Doesn't work. What datapath width do we need for the udp user port?
        self.submodules.etherbone = LiteEthEtherbone(
            udp=self.ethcore.udp,
            udp_port=1234,
            buffer_depth=8,
            cd="sys",
            dw=D * 8
        )
        self.bus.add_master(master=self.etherbone.wishbone.bus)

    #     # Litescope, add signals to probe here
    #     debug = [
    #         self.ethphy.core_status,
    #         self.ethphy.qplllock_out,
    #         self.ethphy.areset_datapathclk_out
    #     ]
    #     self.submodules.analyzer = LiteScopeAnalyzer(debug, 512)

    # def do_exit(self, vns):
    #     self.analyzer.export_csv(vns, "build/analyzer.csv")



def main():
    soc = TestSoc()
    soc.platform.name = 'hello_10G'
    builder = Builder(
        soc,
        compile_gateware='synth' in argv,
        csr_csv='./build/csr.csv',
        csr_json='./build/csr.json',
    )
    if ('build' in argv) or ('synth' in argv):
        builder.build()

    if 'load' in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(join(
            builder.gateware_dir,
            soc.platform.name + ".bit"
        ))


if __name__ == "__main__":
    main()
