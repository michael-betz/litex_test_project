"""
hello_LTC.py runs on fpga, reads ADC data, waits for a trigger
and then dumps 4096 samples in a buffer.
Buffer is read out through litex_server (etherbone) periodically,
fft'ed and plotted.
"""
from time import sleep
from numpy import *
from matplotlib.pyplot import *
from matplotlib.animation import FuncAnimation
from scipy.signal import periodogram
import threading
import argparse
import os
sys.path.append("../..")
from common import *


def autoBitslip(r):
    '''
    resets IDELAY to the middle,
    fires bitslips until the frame signal reads 0xF0
    '''
    setIdelay(r, 16)
    for i in range(8):
        val = r.regs.lvds_frame_peek.read()
        if val == 0xF0:
            print("autoBitslip(): aligned after", i)
            return
        r.regs.lvds_bitslip_csr.write(1)
    raise RuntimeError("autoBitslip(): failed alignment :(")


def setIdelay(r, target_val):
    '''
    increments / decrements IDELAY to reach target_val
    '''
    val = r.regs.lvds_idelay_value.read()
    val -= target_val
    if val > 0:
        for i in range(val):
            r.regs.lvds_idelay_dec.write(1)
    else:
        for i in range(-val):
            r.regs.lvds_idelay_inc.write(1)


def autoIdelay(r):
    '''
    testpattern must be 0x01
    bitslips must have been carried out already such that
    data_peek reads 0x01
    '''
    # approximately center the idelay first
    setIdelay(r, 16)

    # decrement until the channels break
    for i in range(32):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 != 1 or val1 != 1:
            break
        r.regs.lvds_idelay_dec.write(1)
    minValue = r.regs.lvds_idelay_value.read()

    # step back up a little
    for i in range(5):
        r.regs.lvds_idelay_inc.write(1)

    # increment until the channels break
    for i in range(32):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 != 1 or val1 != 1:
            break
        r.regs.lvds_idelay_inc.write(1)
    maxValue = r.regs.lvds_idelay_value.read()

    # set idelay to the sweet spot in the middle
    setIdelay(r, (minValue + maxValue) // 2)

    print('autoIdelay(): min = {:}, mean = {:}, max = {:} idelays'.format(
        minValue,
        r.regs.lvds_idelay_value.read(),
        maxValue
    ))

def getSamples(r, CH, N=None):
    addr = getattr(r.mems, 'sample{:}'.format(CH)).base
    samples = array(r.big_read(addr, N))
    return twos_comps(samples, 14) / 2**13

class ScopeController:
    def __init__(self, r):
        self._trigRequest = True
        self._trigLevelRequest = 0
        self._curTrigLevel = None
        self._autoTrigger = True
        self._forceTrig = False
        self.isRunning = True
        self.r = r
        # last 32 blocks of samples for dumping to .npz file
        self.rollBuffer_t = []
        self.rollBuffer_f = []


    def forceTrig(self, e):
        self._forceTrig = True

    def trigLevel(self, l):
        self._trigLevelRequest = int(l * (1 << 13))

    def trigRequest(self, e):
        self._trigRequest = True

    def handleSettings(self):
        if self._curTrigLevel is None or \
           self._curTrigLevel != self._trigLevelRequest:
            self.r.regs.acq_trig_level.write(self._trigLevelRequest)
            self._curTrigLevel = self._trigLevelRequest
            print('trigLevel:', hex(self.r.regs.acq_trig_level.read()))

        if self._trigRequest:
            # print("t")
            self.r.regs.acq_trig_csr.write(1)
            self._trigRequest = False
            return True

        if self._forceTrig:
            self.r.regs.acq_trig_force.write(1)
            self.r.regs.acq_trig_force.write(0)
            self._forceTrig = False
        return False

    def buf_append(buf, val):
        if len(buf) >= args.AVG:
            buf.pop(0)
        else:
            print("Buf:", len(buf))
        buf.append(val)

    def dumpNpz(self, x):
        fName = unique_filename("measurements/dump.npz")
        savez_compressed(fName, dat=vstack(self.rollBuffer_t))
        print("wrote {:} buffers to {:}".format(len(self.rollBuffer_t), fName))
        self.rollBuffer_t.clear()
        self.rollBuffer_f.clear()

    def ani_thread(self):
        tReq = False
        while self.isRunning:
            tReq |= self.handleSettings()

            # wait while acquisition is running
            if r.regs.acq_trig_csr.read() >= 1:
                # print('y', end='', flush=True)
                time.sleep(0.2)
                continue

            # only read data after a new acquisition
            if not tReq:
                # print('x', end='', flush=True)
                time.sleep(0.2)
                continue

            # print('z', end='', flush=True)
            yVect = getSamples(r, args.CH, args.N)
            ScopeController.buf_append(
                self.rollBuffer_t,
                yVect
            )
            f, Pxx = periodogram(
                yVect,
                args.fs,
                window='hanning',
                scaling='spectrum',
                nfft=args.N * 2
            )
            ScopeController.buf_append(
                self.rollBuffer_f,
                Pxx
            )
            spect = 10 * log10(mean(self.rollBuffer_f, 0)) + 3
            lt.set_ydata(yVect)
            lf.set_ydata(spect)
            fig.canvas.draw_idle()

            tReq = False

            # Start next acquisition
            if self._autoTrigger:
                self.trigRequest(None)


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    file_name_parts = os.path.splitext(file_name) # returns ('/path/file', '.ext')
    while os.path.isfile(file_name):
        file_name = file_name_parts[0] + '_' + str(counter) + file_name_parts[1]
        counter += 1
    return file_name


def main():
    global fig, lt, lf, r, args, rollBuffer_t
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--N", default=1024, type=int, help="Number of samples per acquisition"
    )
    parser.add_argument(
        "--AVG", default=8, type=int, help="How many buffers to average the spectrum"
    )
    parser.add_argument(
        "--CH", default=0, choices=[0, 1, 2, 3], type=int, help="Which channel to plot"
    )
    parser.add_argument(
        "--fs", default=117.6e6, type=float, help="ADC sample rate [MHz]. Must match hello_LTC.py setting."
    )
    args = parser.parse_args()
    # ----------------------------------------------
    #  Init hardware
    # ----------------------------------------------
    r = conLitexServer('../build/csr.csv')
    print("fs = {:6f} MHz, should be {:6f} MHz".format(
        r.regs.lvds_f_sample_value.read() / 1e6, args.fs / 1e6
    ))
    print("Resetting LTC")
    ltc_spi = LTC_SPI(r)
    ltc_spi.set_ltc_reg(0, 0x80)   # reset the chip
    ltc_spi.setTp(1)
    autoBitslip(r)
    autoIdelay(r)
    r.regs.acq_trig_channel.write(args.CH)

    print("ADC word bits:")
    for i in range(14):
        tp = 1 << i
        ltc_spi.setTp(tp)
        print("{:016b} {:016b}".format(
            tp, r.regs.lvds_data_peek0.read()
        ))
    ltc_spi.set_ltc_reg(3, 0)  # Test pattern off
    ltc_spi.set_ltc_reg(1, (1 << 5))  # Randomizer off, twos complement output

    # ----------------------------------------------
    #  Setup Matplotlib
    # ----------------------------------------------
    sc = ScopeController(r)
    fig, axs = subplots(2, 1, figsize=(10, 6))
    xVect = linspace(0, args.N / args.fs, args.N, endpoint=False)
    yVect = zeros_like(xVect)
    yVect[:2] = [-1, 1]
    f, Pxx = periodogram(yVect, args.fs, nfft=args.N * 2)
    lt, = axs[0].plot(xVect * 1e9, yVect, drawstyle='steps-post')
    lf, = axs[1].plot(f / 1e6, Pxx)
    axs[0].set_xlabel("Time [ns]")
    axs[1].set_xlabel("Frequency [MHz]")
    axs[0].set_ylabel("ADC value [FS]")
    axs[1].set_ylabel("ADC value [dB_FS]")
    axs[0].axis((-100, 8300, -1, 1))
    axs[1].axis((-0.5, 63, -110, -10))

    # GUI slider for trigger level
    sfreq = Slider(
        axes([0.13, 0.9, 0.72, 0.05]),
        'Trigger level',
        -1, 1, -0.001,
        '%1.3f'
    )
    sfreq.on_changed(sc.trigLevel)

    # Checkboxes
    check = Button(axes([0.05, 0.01, 0.2, 0.05]), "Force trigger")
    check.on_clicked(sc.forceTrig)

    # # Single acquisition button
    # bSingle = Button(axes([0.25, 0.01, 0.2, 0.05]), 'Single trig.')
    # bSingle.on_clicked(sc.trigRequest)

    # Buffer dump button
    bDump = Button(axes([0.25, 0.01, 0.2, 0.05]), 'Dump .npz')
    bDump.on_clicked(sc.dumpNpz)

    threading.Thread(target=sc.ani_thread).start()
    show()
    sc.isRunning = False


if __name__ == '__main__':
    main()
