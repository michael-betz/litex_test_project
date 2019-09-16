#!/usr/bin/env python3
"""
Connect litex_server to a verilator emulation for testing and experimenting.
"""
import argparse

from migen import *
from migen.genlib.io import CRG

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores import uart

from litex.soc.interconnect.wishbonebridge import WishboneStreamingBridge


class SimPins(Pins):
    def __init__(self, n=1):
        Pins.__init__(self, "s " * n)


_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8))
    )
]


class SimSoC(SoCCore):
    csr_map_update(SoCCore.csr_map, {"dut"})

    def __init__(
        self,
        **kwargs
    ):
        # Setting sys_clk_freq too low will cause wishbone timeouts !!!
        sys_clk_freq = int(8e6)
        SoCCore.__init__(
            self,
            SimPlatform("SIM", _io),
            clk_freq=sys_clk_freq,
            cpu_type=None,
            integrated_rom_size=0x0,
            integrated_sram_size=0x0,
            ident="LiteX Simulation",
            ident_version=True,
            with_uart=False,
            **kwargs
        )
        # crg
        self.submodules.crg = CRG(self.platform.request("sys_clk"))

        # ----------------------------
        #  Virtual serial to Wishbone bridge
        # ----------------------------
        # virtual serial phy
        self.submodules.uart_phy = uart.RS232PHYModel(
            self.platform.request("serial")
        )
        # bridge virtual serial phy as wishbone master
        self.add_cpu(WishboneStreamingBridge(
            self.uart_phy, sys_clk_freq
        ))
        self.add_wb_master(self.cpu.wishbone)


def main(soc):
    parser = argparse.ArgumentParser(description="LiteX SoC Simulation test")
    builder_args(parser)
    parser.add_argument("--trace", action="store_true",
                        help="enable VCD tracing")
    parser.add_argument("--trace-start", default=0,
                        help="cycle to start VCD tracing")
    parser.add_argument("--trace-end", default=-1,
                        help="cycle to end VCD tracing")
    args = parser.parse_args()

    builder_kwargs = builder_argdict(args)
    builder_kwargs['output_dir'] = 'out'
    builder_kwargs['csr_csv'] = 'out/csr.csv'

    sim_config = SimConfig(default_clk="sys_clk")
    sim_config.add_module("serial2tcp", "serial", args={
        "port": 1111
    })

    builder = Builder(soc, **builder_kwargs)
    builder.build(
        run=False,
        sim_config=sim_config,
        trace=args.trace,
        trace_start=int(args.trace_start),
        trace_end=int(args.trace_end)
    )


if __name__ == "__main__":
    main(SimSoC())
