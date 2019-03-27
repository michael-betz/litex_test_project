SIM_PATH = /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src
SIM_INCLUDES = -y $(SIM_PATH)/unisims

TARGET = IserdesSp6
SRC_V = $(SIM_PATH)/glbl.v $(TARGET).v $(wildcard *.v)

all: $(TARGET).vcd
view: $(TARGET)_view

%.v: %.py
	python3 $^

%_tb: %_tb.v $(SRC_V)
	iverilog $(SIM_INCLUDES) -o $@ $^

%.vcd: %_tb
	vvp -N $< +vcd

%_view: %.vcd %.gtkw
	gtkwave $^

clean:
	rm -rf $(TARGET).vcd $(TARGET).v
