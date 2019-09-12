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
    for i in range(8):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 == 4 and val1 == 4:
            print("autoBitslip(): aligned after", i)
            return
        if val0 != 4:
            r.regs.lvds_bitslip0_csr.write(1)
        if val1 != 4:
            r.regs.lvds_bitslip1_csr.write(1)
    raise RuntimeError("autoBitslip(): failed to align :(")


def autoIdelay(r):
    # approximately center the idelay first
    val = r.regs.lvds_idelay_value.read()
    val -= 16
    if val > 0:
        for i in range(val):
            r.regs.lvds_idelay_dec.write(1)
    else:
        for i in range(-val):
            r.regs.lvds_idelay_inc.write(1)

    # decrement until the channels break
    for i in range(32):
        val0 = r.regs.lvds_data_peek0.read()
        val1 = r.regs.lvds_data_peek2.read()
        if val0 != 4 or val1 != 4:
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
        if val0 != 4 or val1 != 4:
            break
        r.regs.lvds_idelay_inc.write(1)
    maxValue = r.regs.lvds_idelay_value.read()

    # set idelay to the sweet spot in the middle
    for i in range((maxValue - minValue) // 2):
        r.regs.lvds_idelay_dec.write(1)

    print('autoIdelay(): min = {:}, mean = {:}, max = {:} idelays'.format(
        minValue,
        r.regs.lvds_idelay_value.read(),
        maxValue
    ))


def getSamples(r, N=None):
    """ why doesn't RemoteClient take care of chunking for me ??? """
    r_ch = r.mems.sample3
    if N is None:
        N = r_ch.size
    o = r_ch.base
    # r.regs.acq_trig_csr.write(0)
    samples = []
    while N:
        print("read", hex(o), hex(min(255, N)))
        temp = r.read(o, min(255, N))
        o += len(temp) * 4  # in bytes!
        N -= len(temp)
        samples.append(temp)
    samples = hstack(samples)
    return samples / (1 << 15) - 1


def ani_thread():
    while isRunning:
        # print('*', end='', flush=True)
        yVect = getSamples(r, args.N)
        if len(rollBuffer) >= 32:
            rollBuffer.pop(0)
        rollBuffer.append(yVect)
        f, Pxx = periodogram(
            yVect,
            args.fs,
            window='hanning',
            scaling='spectrum',
            nfft=args.N * 2
        )
        spect = 10 * log10(Pxx) + 3
        lt.set_ydata(yVect)
        lf.set_ydata(spect)
        fig.canvas.draw_idle()


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    file_name_parts = os.path.splitext(file_name) # returns ('/path/file', '.ext')
    while os.path.isfile(file_name):
        file_name = file_name_parts[0] + '_' + str(counter) + file_name_parts[1]
        counter += 1
    return file_name


def main():
    global fig, lt, lf, r, args, rollBuffer, isRunning
    isRunning = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--N", default=1024, type=int, help="Number of samples per acquisition"
    )
    parser.add_argument(
        "--fs", default=125e6, type=float, help="ADC sample rate [MHz]. Must match hello_LTC.py setting."
    )
    args = parser.parse_args()
    rollBuffer = []  # last 32 blocks of samples for dumping to .npz file
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

    print("ADC word bits:")
    for i in range(14):
        tp = 1 << i
        ltc_spi.setTp(tp)
        print("{:016b} {:016b}".format(
            tp, r.regs.lvds_data_peek0.read()
        ))
    ltc_spi.set_ltc_reg(3, 0)  # Test pattern off
    ltc_spi.set_ltc_reg(1, 0)  # Randomizer off

    # ----------------------------------------------
    #  Setup Matplotlib
    # ----------------------------------------------
    fig, axs = subplots(2, 1, figsize=(10, 6))
    xVect = linspace(0, args.N / args.fs, args.N, endpoint=False)
    yVect = zeros_like(xVect)
    yVect[:2] = [-1, 1]
    f, Pxx = periodogram(yVect, args.fs, nfft=args.N * 2)
    lt, = axs[0].plot(xVect * 1e9, yVect, "-o")
    lf, = axs[1].plot(f / 1e6, Pxx)
    axs[0].set_xlabel("Time [ns]")
    axs[1].set_xlabel("Frequency [MHz]")
    axs[0].set_ylabel("ADC value [FS]")
    axs[1].set_ylabel("ADC value [dB_FS]")
    axs[0].axis((-100, 8300, -1, 1))
    axs[1].axis((-0.5, 63, -110, -10))
    # GUI slider
    # sfreq = Slider(
    #     axes([0.13, 0.9, 0.72, 0.05]),
    #     'Trigger level',
    #     -1, 1, -0.001,
    #     '%1.3f'
    # )
    # sfreq.on_changed(
    #     lambda l: r.regs.acq_trig_level.write(int((l + 1) * (1 << 15)))
    # )
    bDump = Button(axes([0.13, 0.01, 0.2, 0.05]), 'Dump .npz')
    def dump(x):
        fName = unique_filename("measurements/dump.npz")
        savez_compressed(fName, dat=vstack(rollBuffer))
        print("wrote {:} buffers to {:}".format(len(rollBuffer), fName))
        rollBuffer.clear()
    bDump.on_clicked(dump)
    threading.Thread(target=ani_thread).start()
    show()
    isRunning = False


if __name__ == '__main__':
    main()
