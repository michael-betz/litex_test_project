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
import argparse
import os
sys.path.append("..")
from common import *


def getSamples(r, N=None):
    """ why doesn't RemoteClient take care of chunking for me ??? """
    if N is None:
        N = r.mems.sample.size
    o = r.mems.sample.base
    r.regs.acq_trig_csr.write(0)
    samples = []
    while N:
        temp = r.read(o, min(255, N))
        o += len(temp) * 4  # in bytes!
        N -= len(temp)
        samples.append(temp)
    samples = hstack(samples)
    return samples / (1 << 15) - 1


def ani(i, r, args, lt=None, lf=None, rollBuffer=None):
    yVect = getSamples(r, args.N)
    if rollBuffer is not None:
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
    if lt:
        lt.set_ydata(yVect)
    if lf:
        lf.set_ydata(spect)
    return yVect, f, spect


def unique_filename(file_name):
    """ thank you stack overflow """
    counter = 1
    file_name_parts = os.path.splitext(file_name) # returns ('/path/file', '.ext')
    while os.path.isfile(file_name):
        file_name = file_name_parts[0] + '_' + str(counter) + file_name_parts[1]
        counter += 1
    return file_name


def main():
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
    r = conLitexServer()
    print("fs = {:6f} MHz, should be {:6f} MHz".format(
        r.regs.lvds_f_sample_value.read() / 1e6, args.fs / 1e6
    ))
    print("Resetting LTC")
    ltc_spi = LTC_SPI(r)
    ltc_spi.set_ltc_reg(0, 0x80)   # Software reset
    print("Aligning bits: ", end="")
    for i in range(8):
        rVal = r.regs.lvds_frame_peek.read()
        if rVal == 0xF0:
            break
        else:
            r.regs.lvds_bitslip_csr.write(1)
            print("*", end="")
    if rVal != 0xF0:
        raise RuntimeError("Bitslip error. Want 0x0F, got " + hex(rVal))
    print("done!")
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
    yVect0, fVect, ampsVect = ani(0, r, args, rollBuffer=rollBuffer)
    lt, = axs[0].plot(xVect * 1e9, yVect0, "-o")
    lf, = axs[1].plot(fVect / 1e6, ampsVect)
    axs[0].set_xlabel("Time [ns]")
    axs[1].set_xlabel("Frequency [MHz]")
    axs[0].set_ylabel("ADC value [FS]")
    axs[1].set_ylabel("ADC value [dB_FS]")
    # GUI slider
    sfreq = Slider(
        axes([0.13, 0.9, 0.72, 0.05]),
        'Trigger level',
        -1, 1, -0.001,
        '%1.3f'
    )
    sfreq.on_changed(
        lambda l: r.regs.acq_trig_level.write(int((l + 1) * (1 << 15)))
    )
    bDump = Button(axes([0.13, 0.01, 0.2, 0.05]), 'Dump .npz')
    def dump(x):
        fName = unique_filename("measurements/dump.npz")
        savez_compressed(fName, dat=vstack(rollBuffer))
        print("wrote {:} buffers to {:}".format(len(rollBuffer), fName))
        rollBuffer.clear()
    bDump.on_clicked(dump)
    fani = FuncAnimation(fig, ani, interval=300, fargs=(r, args, lt, lf, rollBuffer))
    show()


if __name__ == '__main__':
    main()
