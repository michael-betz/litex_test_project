# SIM_PATH = /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src
# SIM_PATH = /opt/Xilinx/Vivado/2018.2/data/verilog/src
SIM_PATH = /home/michael/vivado/Vivado/2018.3/data/verilog/src
SIM_INCLUDES = -y . -y ./build/gateware -y $(SIM_PATH)/unisims
vpath %.v test
vpath %.gtkw test

%.vcd: %_tb
	vvp -N $< +vcd

#-pfileline=1
%_tb: %_tb.v %.v
	iverilog $(SIM_INCLUDES) -o $@ $< $(SRC_V)

%.v: %.py
	python3 $< build

%.bit: %.py
	python3 $< synth

%_view: %.vcd %.gtkw
	gtkwave $^

all: $(TARGETS:=.vcd)

clean::
	rm -rf $(TARGETS:=.vcd) $(TARGETS:=.v) $(TARGETS:=_tb)
	rm -rf tree0_*.svg

help::
	@echo "all      Run simulation (default)"
	@echo "view     Show sim. results in gtkwave"
	@echo "config   Load bitstream into FPGA"


#-------
# xsim
#-------
# $(TARGET).vcd: $(TARGET)_tb
# 	xsim -nolog -R $< -testplusarg vcd
# $(TARGET)_tb: $(TARGET)_tb.v
# 	xvlog -nolog $(filter %.v,$^)
# 	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns
#
# This worked (once upon a time):
# xvlog hello_ETH_tb.v ./build/gateware/hello_ETH.v /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src/glbl.v hello_ETH_tb.v
# xelab -L unisims_ver hello_ETH_tb glbl
# xsim -R hello_ETH_tb#work.glbl -testplusarg vcd
