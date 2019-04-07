from migen import *

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
