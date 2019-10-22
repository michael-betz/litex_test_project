include ../../../bedrock/dir_list.mk
include $(BUILD_DIR)/top_rules.mk
include $(CORDIC_DIR)/rules.mk

vpath %.v $(CORDIC_DIR) $(DSP_DIR)

TARGET  = dsp

SRC_V  += rot_dds.v cordicg_b22.v cstageg.v addsubg.v ddc.v
SRC_V  += iq_mixer_multichannel.v mixer.v
SRC_V  += multi_sampler.v cic_multichannel.v
SRC_V  += serializer_multichannel.v reg_delay.v ccfilt.v double_inte_smp.v
SRC_V  += doublediff.v serialize.v grab_channels.v

all: $(TARGET).vcd

$(TARGET)_tb: $(SRC_V) $(TARGET).v

plot: $(TARGET).vcd
	python3 quickPlot.py output.txt --skip 100 --ts 8.506805

CLEAN += cordicg_b22.v output.txt

include $(BUILD_DIR)/bottom_rules.mk
