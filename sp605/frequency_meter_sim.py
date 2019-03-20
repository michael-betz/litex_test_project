from migen import *
from litex.gen.sim import *
from litex.soc.cores import frequency_meter

# @passive
# def meas_clk_generator(dut):
#     while True:
#         print(".", end="", flush=True)
#         yield


def main_generator(dut):
    for i in range(101):
        # print("*", end="", flush=True)
        yield
    print("\nFrequencyMeter.value = ", (yield dut.value.status))


dut = frequency_meter.FrequencyMeter(period=100, width=6)
generators = {
    "sys": main_generator(dut),
    # "fmeter": meas_clk_generator(dut)
}
clocks = {
    "sys": 1000,
    "fmeter": 30
}
run_simulation(dut, generators, clocks, vcd_name="sim.vcd")
