from time import sleep
from collections import namedtuple
from spi_helper import AdSpi, HmcSpi
from litejesd204b.common import JESD204BSettings
from litejesd204b.transport import seed_to_data


class Ad9174Settings(JESD204BSettings):
    JM = namedtuple('JESD_MODE', 'L M F S NP N K HD')
    MODES = {
         0: JM(1, 2, 4, 1, 16, 16, 32, 1),
         1: JM(2, 4, 4, 1, 16, 16, 32, 1),
         2: JM(3, 6, 4, 1, 16, 16, 32, 1),
         3: JM(2, 2, 2, 1, 16, 16, 32, 1),
         4: JM(4, 4, 2, 1, 16, 16, 32, 1),
         5: JM(1, 2, 3, 1, 12, 12, 32, 1),
         6: JM(2, 4, 3, 1, 12, 12, 32, 1),
         7: JM(1, 4, 8, 1, 16, 16, 32, 1),
         8: JM(4, 2, 1, 1, 16, 16, 32, 1),
         9: JM(4, 2, 2, 2, 16, 16, 32, 1),
        10: JM(8, 2, 1, 2, 16, 16, 32, 1),
        11: JM(8, 2, 2, 4, 16, 16, 32, 1),
        12: JM(8, 2, 3, 8, 12, 12, 32, 1),
        18: JM(4, 1, 1, 2, 16, 16, 32, 1),
        19: JM(4, 1, 2, 4, 16, 16, 32, 1),
        20: JM(8, 1, 1, 4, 16, 16, 32, 1),
        21: JM(8, 1, 2, 8, 16, 16, 32, 1),
        22: JM(4, 2, 3, 4, 12, 12, 32, 1)
    }

    def __init__(
        self,
        JESD_MODE,
        INTERP_CH=None,
        INTERP_MAIN=None,
        fchk_over_octets=True,
        **kwargs
    ):
        '''
        JESD_MODE:
            a number defining the set of JESD parameters, as commonly used
            by Analog Devices.

        INTERP_CH:
            channelizer datapath interpolation factor

        INTERP_MAIN:
            main datapath interpolation factor

        kwargs:
            individually overwrite JESD parameters
        '''
        self.INTERP_CH = INTERP_CH
        self.INTERP_MAIN = INTERP_MAIN
        self.JESD_MODE = JESD_MODE
        mode_dict = Ad9174Settings.MODES[JESD_MODE]._asdict()
        mode_dict.update(**kwargs)

        super().__init__(fchk_over_octets, **mode_dict)

        self.DSP_CLK_DIV = 0
        if INTERP_CH is not None and INTERP_MAIN is not None:
            # f_DAC / f_PCLK: this is the clock driving the FPGA
            # The division is split over AD9174 (/4) and HMC7044 (/N)
            self.DSP_CLK_DIV = self.L * 32 * INTERP_CH * INTERP_MAIN // \
                self.M // self.NP

            # Assume frequency divider by 4 in hmc7044 is hard-coded
            if (self.DSP_CLK_DIV % 4) > 0:
                raise ValueError('invalid clocking')

        self.calc_fchk()  # first one comes for free

    def __repr__(self):
        s = '----------------\n'
        s += ' JESD mode {}\n'.format(self.JESD_MODE)
        s += '----------------\n'
        s += 'INTERP_CH: {}  INTERP_MAIN: {}  DSP_CLK_DIV: {}\n'.format(
            self.INTERP_CH, self.INTERP_MAIN, self.DSP_CLK_DIV
        )
        s += super().__repr__()
        return s

    def export_constants(self, soc):
        '''
        export all settings as litex constants, which will be written to
        csr.csv / csr.json
        '''
        super().export_constants(soc)
        soc.add_constant('JESD_JESD_MODE', self.JESD_MODE)
        soc.add_constant('JESD_INTERP_CH', self.INTERP_CH)
        soc.add_constant('JESD_INTERP_MAIN', self.INTERP_MAIN)
        soc.add_constant('JESD_DSP_CLK_DIV', self.DSP_CLK_DIV)


class Ad9174Init():
    def __init__(self, r, settings):
        '''
        r:
            a litex_remote_server handle for register access

        settings:
            a Ad9174Settings instance
        '''
        self.regs = r.regs
        self.settings = settings
        self.ad = AdSpi(r)
        self.hmc = HmcSpi(r)

    def init_hmc(self):
        hmc = self.hmc
        hmc.init_hmc7044()

        clk_div = self.settings.DSP_CLK_DIV // 4
        hmc.setup_channel(12, clk_div)        # DEV_CLK = 160 MHz
        hmc.setup_channel(3, clk_div * 100)   # SYSREF (DAC) = 1.6 MHz
        hmc.setup_channel(13, clk_div * 100)  # SYSREF (FPGA) = 1.6 MHz
#         hmc.trigger_reseed()
        self.hmc.trigger_div_reset()

    def init_ad9174(self):
        regs = self.regs
        ad = self.ad
        s = self.settings

        # ------------------------
        #  Reset and general init
        # ------------------------
        # disable GTX transceivers
        regs.control_control.write(0)

        # Power up sequence, Table 51
        ad.wr(0x000, 0x81)  # Soft reset
        ad.wr(0x000, 0x3C)  # 4 - wire SPI mode + ADDRINC

        ad.wr(0x091, 0x00)  # Power up clock RX
        ad.wr(0x206, 0x01)  # Bring CDR out of reset
        ad.wr(0x705, 0x01)  # LOAD NVRAM FACTORY SETTINGS
        ad.wr(0x090, 0x00)  # Power on DACs and bias supply
        print('AD917X_NVM_BLR_DONE:', (ad.rr(0x705) >> 1) & 1)

        # Print product ID (0x9174)
        val = ad.rr('SPI_PRODIDH') << 8 | ad.rr('SPI_PRODIDL')
        print('PROD_ID: 0x{:04x}'.format(val))
        val = ad.rr('SPI_CHIPGRADE')
        print('PROD_GRADE: {:x}  DEV_REVISION: {:x}'.format(
            val >> 8, val & 0xF
        ))

        ad.wr(0x100, 0x01)  # Put digital datapath in reset

        # Disable DAC PLL and config for external clock, Table 52
        ad.wr(0x095, 0x01)
        ad.wr(0x790, 0xFF)  # DACPLL_POWER_DOWN
        ad.wr(0x791, 0x1F)

        # ADC clock output divider = /4
        #   0: Divide by 1
        #   1: Divide by 2
        #   2: Divide by 3
        #   3: Divide by 4
        BIT_ADC_CLK_DIVIDER = 6
        ad.wr(0x799, (3 << BIT_ADC_CLK_DIVIDER) | 8)

        # As the clock to the HMC744 is stable now,
        # it's a good time to reset its clock dividers
#         self.hmc.trigger_reseed()  # TODO does not seem to give reproducible delays, why?
        self.hmc.trigger_div_reset()
        # reset FPGA jesd clock domain (disables transceivers)
        regs.ctrl_reset.write(1)
        # Reset CDRs
        ad.wr(0x206, 0x00)
        ad.wr(0x206, 0x01)

        # Delay Lock Loop (DLL) Configuration
        ad.wr(0x0C0, 0x00)  # Power-up delay line.
        ad.wr(0x0DB, 0x00)  # Update DLL settings to circuitry.
        ad.wr(0x0DB, 0x01)
        ad.wr(0x0DB, 0x00)
        ad.wr(0x0C1, 0x68)  # set search mode for f_DAC > 4.5 GHz
        ad.wr(0x0C1, 0x69)  # set DLL_ENABLE
        ad.wr(0x0C7, 0x01)  # Enable DLL read status.
        dll_lock = ad.rr(0x0C3) & 0x01
        print('DLL locked:', dll_lock)
        if dll_lock < 1:
            raise RuntimeError('Delay locked loop not locked :(')

        ad.wr(0x008, (0b01 << 6) | 0b000001)  # Select DAC0, channel0
        print('SPI_PAGEINDX: 0b{:08b}'.format(ad.rr('SPI_PAGEINDX')))

        # Magic numbers from Table 54 (calibration)
        ad.wr(0x050, 0x2A)
        ad.wr(0x061, 0x68)
        ad.wr(0x051, 0x82)
        ad.wr(0x051, 0x83)
        cal_stat = ad.rr(0x052)
        ad.wr(0x081, 0x03)  # Power down calibration clocks
        print('CAL_STAT:', cal_stat)  # 1 = success
        if cal_stat != 1:
            raise RuntimeError('Calibration failed :(')

        # Triggers the GTXInit state machine in FPGA
        regs.control_control.write(1)

        # ---------------------------
        # Table 58, SERDES interface
        # ---------------------------
        # disable serdes PLL, clear sticky loss of lock bit
        ad.wr(0x280, 0x04)
        ad.wr(0x280, 0x00)
        ad.wr(0x200, 0x01)  # Power down the entire JESD204b receiver analog (all eight channels and bias)

        # EQ settings for < 11 dB insertion loss
        ad.wr(0x240, 0xAA)
        ad.wr(0x241, 0xAA)
        ad.wr(0x242, 0x55)
        ad.wr(0x243, 0x55)
        ad.wr(0x244, 0x1F)
        ad.wr(0x245, 0x1F)
        ad.wr(0x246, 0x1F)
        ad.wr(0x247, 0x1F)
        ad.wr(0x248, 0x1F)
        ad.wr(0x249, 0x1F)
        ad.wr(0x24A, 0x1F)
        ad.wr(0x24B, 0x1F)

        # Power down the unused PHYs
        # when L is 3, the first 3 lanes stay powered up
        ad.wr(0x201, 0xFF - 2**s.L + 1)
        ad.wr(0x203, 0x00)  # don't power down sync0, sync1
        ad.wr(0x253, 0x01)  # Sync0: 0 = CMOS, 1 = LVDS
        ad.wr(0x254, 0x01)  # Sync1: 0 = CMOS, 1 = LVDS

        # SERDES required register write.
        ad.wr(0x210, 0x16)
        ad.wr(0x216, 0x05)
        ad.wr(0x212, 0xFF)
        ad.wr(0x212, 0x00)
        ad.wr(0x210, 0x87)
        ad.wr(0x210, 0x87)
        ad.wr(0x216, 0x11)
        ad.wr(0x213, 0x01)
        ad.wr(0x213, 0x00)
        ad.wr(0x200, 0x00)  # Power up the SERDES circuitry blocks.
        sleep(0.1)

        # SERDES required register write.
        ad.wr(0x210, 0x86)
        ad.wr(0x216, 0x40)
        ad.wr(0x213, 0x01)
        ad.wr(0x213, 0x00)
        ad.wr(0x210, 0x86)
        ad.wr(0x216, 0x00)
        ad.wr(0x213, 0x01)
        ad.wr(0x213, 0x00)
        ad.wr(0x210, 0x87)
        ad.wr(0x216, 0x01)
        ad.wr(0x213, 0x01)
        ad.wr(0x213, 0x00)
        ad.wr(0x280, 0x05)

        # Start up SERDES PLL and initiate calibration
        ad.wr(0x280, 0x01)
        pll_locked = ad.rr(0x281) & 0x01
        print('SERDES PLL locked:', pll_locked)
        if pll_locked != 1:
            raise RuntimeError("SERDES PLL not locked")

        # Setup deterministic latency buffer release delay
#         ad.wr(0x304, 0x03)  # LMFC_DELAY_0 for link0 [PCLK cycles]
#         ad.wr(0x305, 0x03)  # LMFC_DELAY_1 for link1 [PCLK cycles]
#         ad.wr(0x306, 0x0C)  # LMFC_VAR_0  variable delay buffer, max is 0x0C
#         ad.wr(0x307, 0x0C)  # LMFC_VAR_1

        # Enable all interrupts
        ad.wr('JESD_IRQ_ENABLEA', 0xFF)
        ad.wr('JESD_IRQ_ENABLEB', 1)  # config mismatch interrupt
        ad.wr('IRQ_ENABLE', 0xFF)
        ad.wr('IRQ_ENABLE0', 0xFF)
        ad.wr('IRQ_ENABLE1', 0xFF)
        ad.wr('IRQ_ENABLE2', 0xFF)

        # ---------------------
        # JESD init
        # ---------------------
        ad.wr(0x100, 0x00)  # Power up digital datapath clocks
        ad.wr(0x110, (0 << 5) | s.JESD_MODE)  # 0 = single link

        ad.wr(0x111, (s.INTERP_MAIN << 4) | s.INTERP_CH)
        mode_not_in_table = (ad.rr(0x110) >> 7) & 0x01
        print('MODE_NOT_IN_TABLE:', mode_not_in_table)
        if mode_not_in_table:
            raise RuntimeError('JESD mode / interpolation factors not valid')

        ad.wr(0x084, (0 << 6))  # SYSREF_PD: 0 = AC couple, don't power down
        ad.wr(0x300, 0b0001)  # select single link, page link0, enable link0
        ad.wr(0x475, 0x09)  # Soft reset the JESD204B quad-byte deframer

        # Write JESD settings blob to AD9174 registers
        for i, o in enumerate(s.octets):
            ad.wr(0x450 + i, o)

        # bit0 checksum method: 0 = sum fields (seems buggy), 1 = sum registers
        ad.wr('CTRLREG1', 0x11)
        ad.wr('ERRORTHRES', 0x01)  # Error threshold
        ad.wr(0x475, 1)  # Bring the JESD204B quad-byte deframer out of reset.

        # Enable the sync logic, and set the rotation mode to reset
        # the synchronization logic upon a sync reset trigger.
        ad.wr(0x03B, 0xF1)  # enable sync circuit (no datapath ramping)
        ad.wr(0x039, 0x01)  # Allowed ref jitter window (DAC clocks)
        ad.wr(0x036, 0xFF)  # ignore the first 255 sysref edges
        self.trigger_jref_sync()

        # Reset all status interrupts
        ad.wr('JESD_IRQ_STATUSA', 0xFF)
        ad.wr('JESD_IRQ_STATUSB', 1)
        ad.wr('IRQ_STATUS', 0xFF)
        ad.wr('IRQ_STATUS0', 0xFF)
        ad.wr('IRQ_STATUS1', 0xFF)
        ad.wr('IRQ_STATUS2', 0xFF)

        # TODO: Table 56, setup channel datapath
        # TODO: Table 57, setup main datapath

    def trigger_jref_sync(self):
        '''
        Re-aligns the LMFC with the sysref signal.
        Will also shutdown and re-initialize the link.
        '''
        ad = self.ad
        ad.wr(0x03a, 0)
        ad.wr(0x03a, 2)   # trigger one shot sync
        sync_done = (ad.rr(0x3a) >> 4) & 1
        print('SYNC_ROTATION_DONE', sync_done)
        if not sync_done:
            raise RuntimeError('Sync. of LMFC with JREF failed. JREF missing?')
        print('DYN_LINK_LATENCY {:2d} cycles'.format(ad.rr(0x302)))

    def print_irq_flags(self, reset=False):
        '''
        print the status of the latched error flags
        and optionally resets them.
        returns True on error
        '''
        def p(name, reset, bit_strs):
            val = self.ad.rr(name)
            isErr = False
            for i, b_str in enumerate(bit_strs):
                if b_str is not None:
                    if val & 1:
                        print('{:}: {:}'.format(name, b_str))
                        isErr = True
                val >>= 1
            if reset:
                self.ad.wr(name, 0xFF)
            return isErr

        isErr = p('JESD_IRQ_STATUSA', reset, [
            'Code Group Sync. failed',
            'Frame Sync. failed',
            'ILAS checksum bad',
            'ILAS failed',
            'Interlane deskew failed',
            'Unexpected K > threshold',
            'Not in table > threshold',
            'Bad disparity > threshold'
        ])

        isErr |= p('JESD_IRQ_STATUSB', reset, [
            'lane0 ILAS config mismatch'
        ])

        isErr |= p('IRQ_STATUS', reset, [
            'DAC0 PRBS error',
            'DAC1 PRBS error',
            'Lane FIFO overflow/underflow',
            'JESD204x receiver not ready',
            'SYSREF jitter too large'
        ])

        isErr |= p('IRQ_STATUS0', reset, [
            'DAC0 Power Amplifier error',
            None, None,
            'DAC0 calibration not done'
        ])

        isErr |= p('IRQ_STATUS1', reset, [
            'DAC1 Power Amplifier error',
            None, None,
            'DAC1 calibration not done'
        ])

        isErr |= p('IRQ_STATUS2', reset, [
            'DAC PLL locked',
            'DAC PLL lock lost',
            None, None,
            'DLL locked',
            'DLL lost'
        ])

        return isErr

    def print_fpga_clocks(self):
        ''' Print measured clock frequency in FPGA '''
        f_jesd = self.regs.crg_f_jesd_value.read()
        f_ref = self.regs.f_ref_value.read()
        print('f_device = {:.6f} MHz  f_ref = {:.6f} MHz'.format(
            f_jesd / 1e6, f_ref / 1e6
        ))

    def print_phy_snapshot(self):
        ''' print one received word of the AD9174 JESD PHYs '''
        ad = self.ad
        ad.wr('PHY_PRBS_TEST_EN', 0xFF)  # Needed: clock to test module
        ad.wr('PHY_PRBS_TEST_CTRL', 0b01)  # rst

        print('PHY_SNAPSHOT_DATA:')
        for lane in range(self.settings.L):
            ad.wr('PHY_PRBS_TEST_CTRL', (lane << 4))
            ad.wr('PHY_DATA_SNAPSHOT_CTRL', 0x01)
            ad.wr('PHY_DATA_SNAPSHOT_CTRL', 0x00)
            val = 0
            for i in range(5):
                val = (val << 8) | ad.rr(0x323 - i)
            bVal = '{:040b}'.format(val)
            print('{0:}: 0x{1:010x}, 0b{2:}'.format(lane, val, bVal))

    def print_ilas(self):
        print("JESD settings, received on lane 0 vs (programmed):")
        # FCHK_N = 1:
        # Checksum is calculated by summing the registers containing the packed
        # link configuration fields
        # (sum of Register 0x450 to Register 0x45A, modulo 256).
        chk_rx = 0
        chk_prog = 0
        cfg_mismatch = False
        for i in range(0x400, 0x40E):
            rx_val = self.ad.rr(i)
            prog_val = self.ad.rr(i + 0x50)
            if (i >= 0x400) and (i <= 0x40a):
                chk_rx += rx_val
                chk_prog += prog_val
            print('{:03x}: {:02x} ({:02x})'.format(i + 0x50, rx_val, prog_val))
            if rx_val != prog_val:
                cfg_mismatch = True
        print('CHK: {:02x} ({:02x}) {:}'.format(chk_rx & 0xFF, chk_prog & 0xFF, 'config mismatch!' if cfg_mismatch else ''))

    def print_lane_status(self):
        def st(n, fmt='08b'):
            print('{:>17s}: {:{:}}'.format(n, self.ad.rr(n), fmt))

        print('\nLane status:')
        st('LANE_DESKEW')
        st('BAD_DISPARITY')
        st('NOT_IN_TABLE')
        st('UNEXPECTED_KCHAR')
        st('CODE_GRP_SYNC')
        st('FRAME_SYNC')
        st('GOOD_CHECKSUM')
        st('INIT_LANE_SYNC')
        st('FIFO_STATUS_REG_0')
        st('FIFO_STATUS_REG_1')

        print('fpga j_sync errs: {:}'.format(
            self.regs.control_jsync_errors.read()
        ))

    def test_stpl(self, wait_secs=1):
        print('STPL test:')
        ad = self.ad
        self.regs.control_stpl_enable.write(1)

        sample = 0  # 0 - 15  TODO implement support for multiple samples
        for converter in range(self.settings.M):
            channel = converter // 2  # 0 - 2
            i_q = converter % 2
            tp = seed_to_data((converter << 8) | sample)
            # tp = 0x597A  # I
            # tp = 0xD27A  # Q

            cfg = (sample << 4) | (channel << 2)
            ad.wr(0x32c, cfg)         # select sample and chanel, disable
            ad.wr(0x32e, tp >> 8)
            ad.wr(0x32d, tp & 0xFF)
            ad.wr(0x32f, (i_q << 6))    # 0: I,  1: Q
            ad.wr(0x32c, cfg | 0x01)  # enable
            ad.wr(0x32c, cfg | 0x03)  # reset
            ad.wr(0x32c, cfg | 0x01)  # run
            sleep(wait_secs)
            is_fail = ad.rr('SHORT_TPL_TEST_3') & 1
            print('converter: {:}, tp: {:04x}, fail: {:}'.format(
                converter, tp, is_fail
            ))

        self.regs.control_stpl_enable.write(0)
