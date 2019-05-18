vpath %.bit build/gateware/
vpath %.bit.bin build/gateware/
TARGETS = hello_LTC

# Upload to the zedboard via scp and program the PL
upload: $(TARGETS).bit.bin
	./config_remote.sh $<

%.bit.bin: %.bit
	python3 bitstream_fix.py $<

include ../rules.mk

clean::
	# in ip, delete everything except .xci
	find ip ! -name 'processing_system7_0.xci' -type f -exec rm -f {} +
