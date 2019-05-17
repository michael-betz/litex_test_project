from sys import argv, exit
from litex.soc.integration.builder import Builder
from litex import RemoteClient
from os import system
from struct import pack, unpack
from numpy import *
from matplotlib.pyplot import *
from scipy.signal import *
from migen import *
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc


ltc_pads = [
    ("LTC_SPI", 0,
        Subsignal("cs_n", Pins("LPC:LA14_P")),
        Subsignal("miso", Pins("LPC:LA14_N"), Misc("PULLUP")),
        Subsignal("mosi", Pins("LPC:LA27_P")),
        Subsignal("clk",  Pins("LPC:LA27_N")),
        IOStandard("LVCMOS25")
    ),
    ("LTC_OUT", 0,  # Bank 0
        Subsignal("a_p", Pins("LPC:LA03_P")),
        Subsignal("a_n", Pins("LPC:LA03_N")),
        Subsignal("b_p", Pins("LPC:LA08_P")),
        Subsignal("b_n", Pins("LPC:LA08_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 1,  # Bank 0
        Subsignal("a_p", Pins("LPC:LA12_P")),
        Subsignal("a_n", Pins("LPC:LA12_N")),
        Subsignal("b_p", Pins("LPC:LA16_P")),
        Subsignal("b_n", Pins("LPC:LA16_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 2,  # Bank 2
        Subsignal("a_p", Pins("LPC:LA22_P")),
        Subsignal("a_n", Pins("LPC:LA22_N")),
        Subsignal("b_p", Pins("LPC:LA25_P")),
        Subsignal("b_n", Pins("LPC:LA25_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_OUT", 3,  # Bank 2
        Subsignal("a_p", Pins("LPC:LA29_P")),
        Subsignal("a_n", Pins("LPC:LA29_N")),
        Subsignal("b_p", Pins("LPC:LA31_P")),
        Subsignal("b_n", Pins("LPC:LA31_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_FR", 0,  # Bank 2
        Subsignal("p", Pins("LPC:LA18_CC_P")),
        Subsignal("n", Pins("LPC:LA18_CC_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    ),
    ("LTC_DCO", 0,  # Bank 2
        Subsignal("p", Pins("LPC:LA17_CC_P")),
        Subsignal("n", Pins("LPC:LA17_CC_N")),
        IOStandard("LVDS_25"),
        Misc("DIFF_TERM=TRUE")
    )
]

class LedBlinker(Module):
    def __init__(self, f_clk=100e6):
        """
        for debugging clocks
        toggles output at 1 Hz
        use ClockDomainsRenamer()!
        """
        self.out = Signal()

        ###

        max_cnt = int(f_clk / 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync += [
            cntr.eq(cntr + 1),
            If(cntr == max_cnt,
                cntr.eq(0),
                self.out.eq(~self.out)
            )
        ]


def main(soc, doc=''):
    """ generic main function for litex modules """
    if len(argv) < 2:
        print(doc)
        exit(-1)
    tName = argv[0].replace(".py", "")
    vns = None
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(
            build_name=tName, regular_comb=False, blocking_assign=True
        )
        # Ugly workaround as I couldn't get vpath to work :(
        system('cp ./build/gateware/mem*.init .')
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=True, compile_software=True
        )
        vns = builder.build(build_name=tName)
    if "config" in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
    print(vns)
    try:
        soc.do_exit(vns)
    except:
        pass


#-----------------------
# litex_server stuff
#-----------------------
def getId(r):
    s = ""
    for i in range(64):
        temp = r.read(r.bases.identifier_mem + i * 4)
        if temp == 0:
            break
        s += chr(temp & 0xFF)
    return s


def conLitexServer(csr_csv="build/csr.csv", port=1234):
    for i in range(32):
        try:
            r = RemoteClient(csr_csv=csr_csv, debug=False, port=port + i)
            r.open()
            print("Connected to Port", 1234 + i)
            break
        except ConnectionRefusedError:
            r = None
    if r:
        print(getId(r))
    else:
        print("Could not connect to RemoteClient")
    return r


class LTC_SPI:
    # config bits
    OFFLINE = 0  # all pins high-z (reset=1)
    CS_POLARITY = 3  # active level of chip select (reset=0)
    CLK_POLARITY = 4  # idle level of clk (reset=0)
    CLK_PHASE = 5  # first edge after cs assertion to sample data on (reset=0)
    LSB_FIRST = 6  # LSB is the first bit on the wire (reset=0)
    HALF_DUPLEX = 7  # 3-wire SPI, in/out on mosi (reset=0)
    DIV_READ = 16  # SPI read clk divider (reset=0)
    DIV_WRITE = 24  # f_clk / f_spi_write == div_write + 2
    # xfer bits
    CS_MASK = 0  # Active high bit mask of chip selects to assert (reset=0)
    WRITE_LENGTH = 16  # How many bits to write and ...
    READ_LENGTH = 24  # when to switch over in half duplex mode

    def __init__(self, r):
        self.r = r
        r.regs.spi_config.write(
            (0xFF << LTC_SPI.DIV_WRITE) |
            (0xFF << LTC_SPI.DIV_READ)
        )
        # 16 bit write transfer (includes read as is 4 wire)
        r.regs.spi_xfer.write(
            (0 << LTC_SPI.READ_LENGTH) |
            (0x10 << LTC_SPI.WRITE_LENGTH) |
            (0xFFFF << LTC_SPI.CS_MASK)
        )

    def set_ltc_reg(self, adr, val):
        word = (0 << 15) | ((adr & 0x7F) << 8) | (val & 0xFF)
        word <<= 16
        self.r.regs.spi_mosi_data.write(word)
        self.r.regs.spi_start.write(1)

    def get_ltc_reg(self, adr):
        word = (1 << 15) | ((adr & 0x7F) << 8)
        word <<= 16
        self.r.regs.spi_mosi_data.write(word)
        self.r.regs.spi_start.write(1)
        return self.r.regs.spi_miso_data.read() & 0xFF

    def setTp(self, tpValue):
        # Test pattern on + value MSB
        self.set_ltc_reg(3, (1 << 7) | tpValue >> 8)
        # Test pattern value LSB
        self.set_ltc_reg(4, tpValue & 0xFF)


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]


def getInt32(I):
    """
    recover sign from twos complement integer
    >>> getInt32(0xFFFFFFFF)
    -1
    """
    return unpack("i", pack("I", I))[0]


def getNyquist(f, fs):
    """ where does a undersampled tone end up? """
    f_n = f / fs
    f_fract = f_n % 1
    if f_fract <= 0.5:
        return f_fract * fs
    else:
        return (1 - f_fract) * fs


def printPd(r):
    """ read iserdes phase detectors, -1 < val < 1 """
    integr = r.regs.lvds_pd_period_csr.read()
    val0 = getInt32(r.regs.lvds_pd_phase_0.read()) / integr
    val1 = getInt32(r.regs.lvds_pd_phase_1.read()) / integr
    print("\r{:0.3f}  {:0.3f}          ".format(val0, val1), end="")
    return val0, val1


def plotNpz(fNames, labels=None, ax=None, fs=120e6, *args, **kwargs):
    """
    plot a .npz dump from scope_app.py
    args, kwargs are passed to plot()
    """
    if ax is None:
        fig, ax = subplots(figsize=(9, 5))
    else:
        fig = gcf()
    if labels is None:
        labels = fNames
    for fName, label in zip(fNames, labels):
        if fName == "fullscale":
            d = sin(arange(4095))
            dat = vstack([d, d])
        else:
            dat = load(fName)["dat"]
        f, Pxx = periodogram(dat, fs, window='hanning', scaling='spectrum', nfft=2**15)
        plot(f / 1e6, 10*log10(mean(Pxx, 0)) + 3, label=label, *args, **kwargs)
    ax.legend()
    ax.set_xlabel("Frequency [MHz]")
    ax.set_ylabel("[db_fs]")
    fig.tight_layout()
