from migen import *

class SpiSlave(Module):
    def __init__(self):
        self.clk = Signal()
        self.mosi = Signal()
        self.miso = Signal()
        self.csn = Signal(reset=1)

        # # #

        isRead = Signal()
        addr = Signal(7)
        cycle = Signal(32)
        clkd = Signal()
        temp = Signal(8)

        self.sync += [
            clkd.eq(self.clk),
            If(self.csn,
                cycle.eq(0)
            ),
            If(self.csn == 0 and clkd == 0 and self.clk,
                If(cycle == 0,
                    isRead.eq(self.mosi)
                ).Elif(cycle <= 7,
                    addr.eq(Cat(addr[:-1], self.mosi))
                ).Else(
                    If(cycle == 8,
                        temp.eq(0x42),
                    ).Elif(cycle >= 15,
                        cycle.eq(8),
                        addr.eq(addr + 1)
                    )
                ),
                cycle.eq(cycle + 1)
            )
        ]


def main():
    print("SPI slave simulation")
    dut = SpiSlave()

    def clk():
        yield dut.clk.eq(1)
        yield
        yield dut.clk.eq(0)
        yield

    def dut_tb(dut):
        yield dut.csn.eq(1)
        yield dut.mosi.eq(0)
        for i in range(16):
            yield from clk()

        yield dut.csn.eq(0)
        yield dut.isRead.eq(1)
        yield
        for i in range(16):
            yield from clk()

    run_simulation(dut, dut_tb(dut), vcd_name="spi_slave.vcd")


if __name__ == '__main__':
    main()
