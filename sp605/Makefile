SIM_PATH = /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src
SIM_INCLUDES = -y $(SIM_PATH)/unisims

TARGET = hello_LTC
SRC_V = build/gateware/top_synth.v

# Run a post synthesis simulation with ISE and Icarus
all: $(TARGET).vcd

# Show results in gtkwave
view: $(TARGET)_view

# Load bitstream into FPGA
config: $(TARGET).py
	python3 $< config

build/gateware/top_synth.v: $(TARGET).py sp6iserdes_lt/IserdesSp6.py
	python3 $< build

%_tb: %_tb.v $(SRC_V)
	iverilog $(SIM_INCLUDES) -o $@ $^

%.vcd: %_tb
	vvp -N $< +vcd

%_view: %.vcd %.gtkw
	gtkwave $^

clean:
	rm -rf $(TARGET).vcd $(TARGET).v
