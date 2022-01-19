# TODO: QSFP+ control lines:
#   * ModSelL=0 to enable I2C interface
#   * LPMode=0 to disable low power mode (ignored?)
#   * ModPrsL reads 0 when QSFP module is inserted
#   * IntL reads 0 on fault / critical status (to be read over I2C then)
#
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
#   * Or maybe modify the MMC firmware to setup Si570

from sys import argv
from migen import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder
from litex_boards.targets.berkeleylab_marble import BaseSoC
from litex.soc.cores.freqmeter import FreqMeter


def add_ip(platform, name, module_name, config={}, synth=True):
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


class Test(Module, AutoCSR):
    def __init__(self, platform):
        self.xgmii_txd = Signal(64)
        self.xgmii_txc = Signal(8)
        self.xgmii_rxd = Signal(64)
        self.xgmii_rxc = Signal(8)

        ###

        self.platform = platform

        add_ip(
            platform,
            "ten_gig_eth_pcs_pma",
            "pcs_pma",
            {
                "MDIO_Management": False,
                "SupportLevel": 1,
                "baser32": "64bit",
                "refclkrate": 156.25,
                "DClkRate": 156.25,
                "SupportLevel": 1  # Add shared logic to core
            }
        )

        clkmgt_pads = platform.request("clkmgt", 0)
        qsfp_pads = platform.request("qsfp", 0)

        self.coreclk_out = Signal()
        areset_datapathclk_out = Signal()

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

        self.specials.pcs_pma = Instance(
            "pcs_pma",
            i_xgmii_txd=self.xgmii_txd,
            i_xgmii_txc=self.xgmii_txc,
            o_xgmii_rxd=self.xgmii_rxd,
            o_xgmii_rxc=self.xgmii_rxc,

            # 156.25 MHz transceiver clock / reset
            i_refclk_p=clkmgt_pads.p,
            i_refclk_n=clkmgt_pads.n,
            i_reset=ResetSignal(),  # Asynchronous Master Reset
            # o_resetdone_out=  # in coreclk_out domain
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
            # o_core_status=  # Bit 0 = PCS Block Lock, Bits [7:1] are reserved

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
        # self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += [
            # self.cd_eth_rx.clk.eq(self.coreclk_out),
            self.cd_eth_tx.clk.eq(self.coreclk_out)
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

    def add_csr(self):
        # Add frequency-meter to 156.25 MHz reference clock
        self.submodules.f_coreclk = FreqMeter(
            period=int(125e6),
            width=4,
            clk=ClockSignal('eth_tx')
        )

        # Config / Status CSRs. 536 bit config reg is challenging for synth.
        self.status = CSRStatus(len(self.status_vector))
        # self.configuration = CSRStorage(len(self.configuration_vector))
        self.comb += [
            self.status.status.eq(self.status_vector),
            # self.configuration_vector.eq(self.configuration.storage)
        ]


class TestSoc(BaseSoC):
    def __init__(self):
        BaseSoC.__init__(
            self,
            cpu_type=None,
            sys_clk_freq=int(125e6),  # TODO test at 200 MHz
            integrated_main_ram_size=8,
            integrated_sram_size=0,
            with_timer=False,
            with_etherbone=False,
            uart_name='uartbone',
            uart_baudrate=1152000  # not a typo
        )
        self.submodules.t = Test(self.platform)
        self.t.add_csr()
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.t.cd_eth_tx.clk,
            # self.t.cd_eth_rx.clk
        )


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
