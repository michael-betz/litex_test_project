TARGETS = hello_ETH
include ../sp605/rules.mk

# For post synth simulation:
#  * make synth
#  * comment the below line
#  * make
#  * make hello_ETH_view
SRC_V += $(SIM_PATH)/glbl.v



#-------
# xsim
#-------
# $(TARGET).vcd: $(TARGET)_tb
# 	xsim -nolog -R $< -testplusarg vcd

# $(TARGET)_tb: $(TARGET)_tb.v
# 	xvlog -nolog $(filter %.v,$^)
# 	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns

# That one worked (once):
# xvlog hello_ETH_tb.v ./build/gateware/hello_ETH.v /opt/Xilinx/14.7/ISE_DS/ISE/verilog/src/glbl.v hello_ETH_tb.v
# xelab -L unisims_ver hello_ETH_tb glbl
# xsim -R hello_ETH_tb#work.glbl -testplusarg vcd


synth:
	python3 $(TARGETS).py synth

config:
	python3 $(TARGETS).py config

clean::
	rm -rf build mem.init

