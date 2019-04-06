TARGET = hello_LTC
SRC_V = build/gateware/top_synth.v
include rules.mk

# Run a post synthesis simulation with ISE and Icarus
# ISE generates a bitfile as a side product
build/gateware/top_synth.v: $(TARGET).py sp6iserdes_lt/IserdesSp6.py dsp/Acquisition.py
	python3 $< build

clean::
	rm -rf build