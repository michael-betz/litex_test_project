from sys import argv
from migen import *
from litex.soc.integration.builder import Builder
from litex_boards.targets.berkeleylab_marble import BaseSoC


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


class Test(Module):
    def __init__(self, platform):
        add_ip(
            platform,
            "ten_gig_eth_pcs_pma",
            "pcs_pma",
            {
                "MDIO_Management": False,
                "SupportLevel": 1,
                "DClkRate": 156.25
            }
        )

        xgmii_txd = Signal(64)
        xgmii_txc = Signal(8)
        configuration_vector = Signal(536)
        clkmgt_pads = platform.request("clkmgt", 0)
        qsfp_pads = platform.request("qsfp", 0)

        self.specials.pcs_pma = Instance(
            "pcs_pma",
            i_dclk=ClockSignal(),
            i_refclk_p=clkmgt_pads.p,
            i_refclk_n=clkmgt_pads.n,
            i_sim_speedup_control=0,
            i_reset=0,
            i_xgmii_txd=xgmii_txd,
            i_xgmii_txc=xgmii_txc,

            # SFP+ SERDES lane
            o_txp=qsfp_pads.tx_p,
            o_txn=qsfp_pads.tx_n,
            i_rxp=qsfp_pads.rx_p,
            i_rxn=qsfp_pads.rx_n,

            i_configuration_vector=configuration_vector,

            i_signal_detect=0,
            i_tx_fault=0,
            i_drp_gnt=0,

            i_drp_den_i=0,
            i_drp_dwe_i=0,
            i_drp_daddr_i=0,
            i_drp_di_i=0,
            i_drp_drdy_i=0,
            i_drp_drpdo_i=0,
            i_pma_pmd_type=0
        )


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


def main():
    soc = TestSoc()
    soc.platform.name = 'hello_udp'
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
