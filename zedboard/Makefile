vpath %.bit build/gateware/
TARGETS = hello_LTC

# Upload to the zedboard via scp and program the PL
upload: $(TARGETS).bit.bin
	util/remote_config_fpga.sh $<

%.bit.bin: %.bit
	python3 util/bitstream_fix.py $<
	mv $<.bin .

include ../rules.mk

clean::
	rm -f $(TARGETS).bit.bin
	rm -rf build
	# in ./ip, delete EVERYTHING except processing_system7_0.xci (a bit harsh, I know ...)
	mv ip/processing_system7_0.xci .
	rm -rf ip/*
	mv processing_system7_0.xci ip
