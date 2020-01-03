from sys import argv
from migen import *
from litex.soc.interconnect.stream import *


class LatchN(PipelinedActor):
    def __init__(self, layout_from, latch_indexes):
        n = len(latch_indexes)
        self.sink = sink = Endpoint(layout_from)
        description_to = copy(sink.description)
        description_to.payload_layout = pack_layout(
            description_to.payload_layout, n
        )
        self.source = source = Endpoint(description_to)
        print(source)

        PipelinedActor.__init__(self, 1)
        self.sync += \
            If(self.pipe_ce,
                self.source.payload.eq(self.sink.payload),
                self.source.param.eq(self.sink.param)
            )


class Adc(Module):
    def __init__(self):
        self.source = source = Endpoint([("data", 14)])
        cnt = Signal(5)
        self.sync += [
            cnt.eq(cnt + 1),
            If(cnt > 25,
                cnt.eq(0)
            )
        ]
        self.comb += [
            source.data.eq(cnt),
            If(cnt <= 7,
                source.valid.eq(1)
            ),
            source.first.eq(cnt == 0),
            source.last.eq(cnt == 7)
        ]


class Cordic(PipelinedActor):
    W = 21  # Width of the cordic
    LAT = W + 2  # Latency

    def __init__(self):
        self.sink = Endpoint([("data", 14)])
        self.source = Endpoint([
            ("mag", Cordic.W),
            ("phase", Cordic.W + 1)
        ])

        ###

        # Cordic mockup (just a delay)
        sig_in = self.sink.data
        for i in range(Cordic.LAT):
            temp = Signal.like(sig_in)
            self.sync += temp.eq(sig_in)
            sig_in = temp
        self.comb += [
            self.source.mag.eq(sig_in),
            self.source.phase.eq(7 - sig_in)
        ]

        super().__init__(Cordic.LAT)


class Dut(Module):
    def __init__(self):
        self.submodules.adc = Adc()
        self.submodules.cordic = Cordic()
        self.submodules.pack = Pack([("mag", Cordic.W)], 8)
        self.submodules.latchN = LatchN([("data", 14)], [0])
        self.comb += [
            self.adc.source.connect(self.cordic.sink),
            self.adc.source.connect(self.latchN.sink),
            self.cordic.source.connect(self.pack.sink, omit=['phase']),
            self.pack.source.ready.eq(1),
            self.latchN.source.ready.eq(1)
        ]


def dut_gen(dut):
    for i in range(64):
        yield


def main():
    tName = argv[0].replace('.py', '')
    dut = Dut()
    if 'build' in argv:
        ''' generate a .v file for simulation with Icarus / general usage '''
        from migen.fhdl.verilog import convert
        convert(
            dut,
            ios={

            },
            display_run=True
        ).write(tName + '.v')
    if "sim" in argv:
        run_simulation(
            dut,
            dut_gen(dut),
            vcd_name=tName + '.vcd'
        )


if __name__ == '__main__':
    if len(argv) <= 1:
        print(__doc__)
        exit(-1)
    main()
