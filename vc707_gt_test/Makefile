# TARGETS = hello_hmc
TARGETS = gt_test

all: build/gateware/$(TARGETS).bit

upload: $(TARGETS).py
	python3 $^ config

server:
	litex_server --uart --uart-port /dev/ttyUSB0 --uart-baudrate 1152000

clean::
	rm -f $(TARGETS).bit
	rm -rf build

include ../rules.mk
