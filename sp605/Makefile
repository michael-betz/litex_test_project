TARGETS = hello_LTC

# For post synth simulation:
#  * make synth
#  * comment the below line
#  * make
#  * make hello_LTC_view
SRC_V += $(SIM_PATH)/glbl.v

all: build/gateware/$(TARGETS).bit

clean::
	rm -rf build mem.init

include ../rules.mk
