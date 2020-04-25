# TARGET = hello_hmc
TARGET = gt_test

all: build/gateware/$(TARGET).bit

upload: build/gateware/$(TARGET).bit
	xc3sprog -v -c jtaghs1_fast $^

server:
	litex_server --uart --uart-port /dev/ttyUSB0 --uart-baudrate 1152000

deploy:
# 	build/gateware/$(TARGET).bit
	rsync --progress -r build donut.dhcp.lbl.gov:~/fpga_wsp/litex_test_project/vc707_gt_test

clean::
	rm -f $(TARGET).bit
	rm -rf build

include ../rules.mk
