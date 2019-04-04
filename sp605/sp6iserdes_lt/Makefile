TARGET = IserdesSp6
SRC_V = $(SIM_PATH)/glbl.v $(TARGET).v $(wildcard *.v)
include ../rules.mk

#-------
# xsim
#-------
# $(TARGET).vcd: $(TARGET)_tb
# 	xsim -nolog -R $< -testplusarg vcd

# $(TARGET)_tb: $(TARGET)_tb.v
# 	xvlog -nolog $(filter %.v,$^)
# 	#xvhdl -nolog $(filter %.vhd,$^)
# 	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns
