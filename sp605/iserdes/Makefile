vpath %.v test
vpath %.gtkw test

TARGETS = sp6_pll sp6_ddr
TARGET = $(word 1,$(TARGETS))

include ../rules.mk

sp6_pll_tb: $(SIM_PATH)/glbl.v
sp6_ddr_tb: $(SIM_PATH)/glbl.v
