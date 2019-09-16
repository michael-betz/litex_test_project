from migen import *
from sim_soc import SimSoC, main
from litex.soc.interconnect.csr import AutoCSR, CSRStatus
from litex.soc.cores.bitbang import I2CMaster


class SimI2c(SimSoC, AutoCSR):
    '''
    Device under test
    I2C master with litex I2CMaster bitbang class
    '''

    def __init__(self):
        SimSoC.__init__(self)
        self.platform.add_source("I2C_slave.v")

        # For making sure csr registers are read back correctly
        self.status_test = CSRStatus(8)
        self.comb += self.status_test.status.eq(0xDE)

        # For testing bit-banging I2C
        self.submodules.i2c_master = m = I2CMaster()

        # Hardwire SDA line to High!!!
        # self.comb += m.pads.sda.eq(0)

        # The simulated I2C slave
        self.specials += Instance(
            "I2C_slave",
            io_scl=m.pads.scl,
            io_sda=m.pads.sda,
            i_clk=ClockSignal(),
            i_rst=ResetSignal(),
            i_data_to_master=0xAF
        )


if __name__ == "__main__":
    main(SimI2c())
