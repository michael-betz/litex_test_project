TARGETS = hello_LTC

all: $(TARGETS).bit.bin

%.bit.bin: build/gateware/%.bit
	python3 util/bitstream_fix.py $<
	mv $<.bin .

# Upload to the zedboard via scp and program the PL
upload:
	util/remote_config_fpga.sh $(TARGETS).bit.bin

server:
	util/remote_litex_server.sh

clean::
	rm -f $(TARGETS).bit.bin
	rm -rf build
	rm -f mem.init
	rm -f mem_?.init
	# in ./ip, delete EVERYTHING except processing_system7_0.xci (a bit harsh, I know ...)
	mv ip/processing_system7_0.xci .
	rm -rf ip/*
	mv processing_system7_0.xci ip

include ../rules.mk
