SIM_PATH = /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src
SIM_INCLUDES = -y $(SIM_PATH)/unisims

%.vcd: %_tb
	vvp -N $< +vcd +VCD_FILE=$@

# -pfileline=1
%_tb: %_tb.v %.v
	iverilog $(SIM_INCLUDES) -o $@ $^

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

help:
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
# 	#xvhdl -nolog $(filter %.vhd,$^)
# 	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns
