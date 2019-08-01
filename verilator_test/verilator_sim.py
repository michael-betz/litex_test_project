#!/usr/bin/env python3
"""
Connect litex_server to a hardware emulation for testing and experimenting.

I want to connect to a piece of emulated hardware (through verilator)
in the same way as I would connect to real hardware.

  * Add the serial2tcp plugin to verilator such that I can connect to the UART
    from outside
  * Run litex_server to connect to the tcp socket instead to a serial port
    such that I can access the emulated wishbone bus from outside

# Running it

    # all 3 run in separate windows ...
    $ python3 verilator_sim.py
    $ litex_server --uart --uart-port socket://localhost:1111
    $ python3 test.py
    Connected to Port 1234
    LiteX Simulation 2019-07-31 19:58:51

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

    def __init__(
        self,
        **kwargs
    ):
        self.platform = platform = SimPlatform("SIM", _io)
        # Setting sys_clk_freq too low will cause wishbone timeouts !!!
        sys_clk_freq = int(10e6)
        SoCCore.__init__(
            self, platform,
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
        self.submodules.crg = CRG(platform.request("sys_clk"))

        # ----------------------------
        #  Virtual serial to Wishbone bridge
        # ----------------------------
        # virtual serial phy
        self.submodules.uart_phy = uart.RS232PHYModel(
            platform.request("serial")
        )
        # bridge virtual serial phy as wishbone master
        self.add_cpu(WishboneStreamingBridge(
            self.uart_phy, sys_clk_freq
        ))
        self.add_wb_master(self.cpu.wishbone)


def main():
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
    builder_kwargs["csr_csv"] = "csr.csv"

    sim_config = SimConfig(default_clk="sys_clk")
    sim_config.add_module("serial2tcp", "serial", args={
        "port": 1111
    })
    # sim_config.add_module("serial2console", "serial")

    soc = SimSoC()
    builder = Builder(soc, **builder_kwargs)
    builder.build(
        sim_config=sim_config,
        trace=args.trace,
        trace_start=int(args.trace_start),
        trace_end=int(args.trace_end)
    )


if __name__ == "__main__":
    main()
