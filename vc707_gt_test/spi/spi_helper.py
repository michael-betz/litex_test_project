import sys
sys.path.append("../..")
from common import *


class OldSpi:
    '''
    supports 3 wire SPI with the old ../zedboard/spi.py
    '''
    # config bit offsets for Litex SPI core
    OFFLINE = 0      # all pins high-z (reset=1)
    CS_POLARITY = 3  # active level of chip select (reset=0)
    CLK_POLARITY = 4  # idle level of clk (reset=0)
    CLK_PHASE = 5    # first edge after cs assertion to sample data on(reset=0)
    LSB_FIRST = 6    # LSB is the first bit on the wire (reset=0)
    HALF_DUPLEX = 7  # 3-wire SPI, in/out on mosi (reset=0)
    DIV_READ = 16    # SPI read clk divider (reset=0)
    DIV_WRITE = 24   # f_clk / f_spi_write == div_write + 2
    # xfer bit offsets
    CS_MASK = 0      # Active high bit mask of chip selects to assert (reset=0)
    WRITE_LENGTH = 16  # How many bits to write and ...
    READ_LENGTH = 24  # when to switch over in half duplex mode

    def __init__(self, r):
        self.r = r
        r.regs.spi_config.write(
            (1 << OldSpi.HALF_DUPLEX) |
            (0xFF << OldSpi.DIV_WRITE) |
            (0xFF << OldSpi.DIV_READ)
        )

    def rxtx(dat24, cs, isWrite=False):
        if isWrite:
            # 16 bit write + 8 bit write transfer (3 wire SPI)
            r.regs.spi_xfer.write(
                (cs << OldSpi.CS_MASK) |
                (16 + 8 << OldSpi.WRITE_LENGTH) |
                (0 << OldSpi.READ_LENGTH)
            )
        else:
            # 16 bit write + 8 bit read transfer (3 wire SPI)
            r.regs.spi_xfer.write(
                (cs << OldSpi.CS_MASK) |
                (16 << OldSpi.WRITE_LENGTH) |
                (8 << OldSpi.READ_LENGTH)
            )
        self.r.regs.spi_mosi_data.write(dat24)
        self.r.regs.spi_start.write(1)
        return self.r.regs.spi_miso_data.read()


class NewSpi:
    '''
    only supports 4 wire SPI with
    litex/soc/cores/spi.py
    enough for HMC chip in read only mode
    '''
    SPI_CONTROL_START = 0
    SPI_CONTROL_LENGTH = 8
    SPI_STATUS_DONE = 0

    def __init__(self, r):
        self.r = r
        self._ctrl = 24 << NewSpi.SPI_CONTROL_LENGTH
        r.regs.spi_control.write(self._ctrl)

    def rxtx(self, dat24, cs, isWrite=False):
        self.r.regs.spi_mosi.write(dat24 << 8)
        self.r.regs.spi_cs.write(cs)
        self.r.regs.spi_control.write(self._ctrl | 1)
        return self.r.regs.spi_miso.read() & 0xFFFFFF


class HmcSpi(NewSpi):
    def wr(self, adr, val):
        # R/W + W1 + W0 + A[13] + D[8]
        word = (0 << 23) | ((adr & 0x1FFF) << 8) | (val & 0xFF)
        # Send 24 bit / 32 bit starting from MSB
        word <<= 8
        self.rxtx(word, 2, True)

    def rr(self, adr):
        '''
        works with OLD_SPI only and no chance on
        AD9174-FMC-EBZ due to hardware bug:
        https://ez.analog.com/data_converters/high-speed_dacs/f/q-a/115934/ad9174-fmc-ebz-reading-hmc7044-registers-over-fmc
        '''
        word = (1 << 23) | ((adr & 0x1FFF) << 8)
        # Send 24 bit / 32 bit starting from MSB
        word <<= 8
        return self.rxtx(word, 2, False) & 0xFF

    def setupChannel(self, chId, f_div=1):
        '''
            set a channel up for CML mode,
            100 Ohm termination,
            no delays

            chId: channel Id starting at 0
            f_div: frequency divison factor starting at 1
        '''
        reg0 = 0xC8 + 10 * chId

        HP_MODE_EN = 7
        SYNC_EN = 6
        SLIP_EN = 5
        STARTUP_MODE = 2
        MULTISLIP_EN = 1
        CH_EN = 0
        self.wr(
            reg0,
            # High performance mode. Adjusts the divider and buffer
            # bias to improve swing/phase noise at the expense of
            # power.
            (1 << HP_MODE_EN) |
            # Configures the channel to normal mode with
            # asynchronous startup, or to a pulse generator mode
            # with dynamic start-up. Note that this must be set to
            # asynchronous mode if the channel is unused.
            # 0 Asynchronous.
            # 1 Reserved.
            # 2 Reserved.
            # 3 Dynamic.
            (0 << STARTUP_MODE) |
            # Channel enable. If this bit is 0, channel is disabled.
            (1 << CH_EN)
        )

        # 12-bit channel divider setpoint LSB. The divider
        # supports even divide ratios from 2 to 4094. The
        # supported odd divide ratios are 1, 3, and 5. All even and
        # odd divide ratios have 50.0% duty cycle.
        # f_div = 10
        self.wr(reg0 + 1, f_div & 0xFF)
        self.wr(reg0 + 2, (f_div >> 8) & 0x0F)

        # 24 fine delay steps. Step size = 25 ps. Values greater
        # than 23 have no effect on analog delay
        fine_delay = 0
        self.wr(reg0 + 3, fine_delay & 0x1F)

        # 17 coarse delay steps. Step size = 1/2 VCO cycle. This flip
        # flop (FF)-based digital delay does not increase noise
        # level at the expense of power. Values greater than 17
        # have no effect on coarse delay.
        coarse_delay = 0
        self.wr(reg0 + 4, coarse_delay & 0x1F)

        # 12-bit multislip digital delay amount LSB.
        # Step size = (delay amount: MSB + LSB) × VCO cycles. If
        # multislip enable bit = 1, any slip events (caused by GPI,
        # SPI, SYNC, or pulse generator events) repeat the
        # number of times set by 12-Bit Multislip Digital
        # Delay[11:0] to adjust the phase by step size.
        multislip_delay = 0
        self.wr(reg0 + 5, multislip_delay & 0xFF)
        self.wr(reg0 + 6, (multislip_delay >> 8) & 0x0F)

        # Channel output mux selection.
        # 0 Channel divider output.
        # 1 Analog delay output.
        # 2 Other channel of the clock group pair.
        # 3 Input VCO clock (fundamental). Fundamental can also
        #   be generated with 12-Bit Channel Divider[11:0] = 1.
        self.wr(reg0 + 7, 0)

        DRIVER_MODE = 3
        self.wr(
            reg0 + 8,
            # Output driver impedance selection for CML mode.
            # 0 Internal resistor disable.
            # 1 Internal 100 Ω resistor enable per output pin.
            # 2 Reserved.
            # 3 Internal 50 Ω resistor enable per output pin.
            1 |
            # Output driver mode selection.
            # 0 CML mode.
            # 1 LVPECL mode.
            # 2 LVDS mode.
            # 3 CMOS mode.
            (0 << DRIVER_MODE)
        )


class AdSpi(NewSpi):
    def rr(self, adr):
        word = (1 << 23) | ((adr & 0x7FFF) << 8)
        return self.rxtx(word, 1, True) & 0xFF

    def wr(self, adr, val):
        word = (0 << 23) | ((adr & 0x7FFF) << 8) | (val & 0xFF)
        return self.rxtx(word, 1, True)
