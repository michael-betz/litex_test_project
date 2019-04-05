TARGET = Acquisition
SRC_V = $(TARGET).v
include ../rules.mk

$(TARGET).vcd: $(TARGET).py
	python3 $< sim
