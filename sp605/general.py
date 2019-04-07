from migen import *
from litex.build.generic_platform import Subsignal, Pins, IOStandard, Misc

ltc_con = [
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
    ),
    # Connect GPIO_SMA on SP605 with CLK input on 1525A
    # Alternatively, use a Si570 eval board as clock source
    ("ENC_CLK", 0,
        Subsignal("p", Pins("SMA_GPIO:P")),
        Subsignal("n", Pins("SMA_GPIO:N")),
        # Note: the LTC eval board needs to be modded
        # to accept a differential clock
        IOStandard("LVDS_25")
    )
]


def myzip(*vals):
    """
    interleave elements in a flattened list

    >>> myzip([1,2,3], ['a', 'b', 'c'])
    [1, 'a', 2, 'b', 3, 'c']
    """
    return [i for t in zip(*vals) for i in t]


class LedBlinker(Module):
    def __init__(self, clk_in, f_clk=100e6):
        """
        for debugging clocks
        toggles output at 1 Hz
        """
        self.out = Signal()

        ###

        self.clock_domains.cd_led = ClockDomain(reset_less=True)
        self.comb += self.cd_led.clk.eq(clk_in)
        max_cnt = int(f_clk // 2)
        cntr = Signal(max=max_cnt + 1)
        self.sync.led += [
            If(cntr == (max_cnt),
                cntr.eq(0),
                self.out.eq(~self.out)
            ).Else(
                cntr.eq(cntr + 1)
            )
        ]
