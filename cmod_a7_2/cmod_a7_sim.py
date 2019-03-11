"""
Simulate the target with verilator
"""
from migen import *
from litex.soc.integration.builder import Builder, builder_args, builder_argdict
from litex.boards.targets.cmod_a7 import BaseSoC
from litex.build.sim import SimPlatform
from litex.build.generic_platform import Pins, Subsignal
from migen.genlib.io import CRG
from cmod_a7_design_example import MySoc
from litex.build.sim.config import SimConfig
from litex.soc.cores import uart
from liteeth.phy.model import LiteEthPHYModel
from liteeth.core.mac import LiteEthMAC
from litex.soc.integration.soc_core import mem_decoder
import argparse


class SimPins(Pins):
    def __init__(self, n=1):
        Pins.__init__(self, "s " * n)


_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("user_led", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("none", SimPins()),
    ),
    ("eth", 0,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8)),
    )
]


class Platform(SimPlatform):
    default_clk_name = "sys_clk"
    default_clk_period = 1000  # ~ 1MHz

    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

    def do_finalize(self, fragment):
        """ ignore adding a clock constraint """
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    builder_args(parser)
    MySoc.basesoc_args(parser)
    parser.add_argument("--trace", action="store_true",
                        help="enable VCD tracing")
    parser.set_defaults(
        integrated_rom_size=0x8000,
        integrated_main_ram_size=0x8000,
        # integrated_sram_size=0,   # Litex will complain if 0!
        cpu_type="vexriscv",
        platform="cmod_a7_sim",
        clk_freq=int(1e6),
        with_uart=False # We will add our own mock uart
    )
    args = parser.parse_args()
    soc = MySoc(crg=CRG, **vars(args))
    # Push in a fake uart
    soc.submodules.uart_phy = uart.RS232PHYModel(soc.platform.request("serial"))
    soc.submodules.uart = uart.UART(soc.uart_phy)

    sim_config = SimConfig(default_clk="sys_clk")
    # sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": "192.168.1.100"})
    # sim_config.add_module("serial2console", "serial")
    sim_config.add_module("serial2tcp", "serial", args={"port": 55555})
    # now you can do these 2 things to get a terminal
    # telnet localhost 55555
    # litex_term socket://localhost:55555
    # soc.add_constant("TFTP_SERVER_PORT", int(tftp_port))

    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=False, sim_config=sim_config)


if __name__ == "__main__":
    main()
