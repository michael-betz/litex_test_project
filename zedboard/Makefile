vpath %.v test
vpath %.gtkw test
TARGETS = s7_iserdes
include ../rules.mk

SRC_V += $(SIM_PATH)/glbl.v
SRC_V += $(TARGETS).v
SRC_V += $(TARGETS)_tb.v

#-------
# xsim, due to secure ip :(
#-------
$(TARGETS).vcd: $(TARGETS)_tb
	xsim -nolog -R $< -testplusarg vcd

$(TARGETS)_tb: $(SRC_V)
	xvlog -nolog $(filter %.v,$^)
	xelab -nolog -L unisims_ver -L secureip $@ glbl -s $@ -timescale 1ns/1ns

clean::
	rm -rf webtalk* vivado.* xsim.dir .Xil *.pb *.jou
