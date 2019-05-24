TARGETS = hello_LTC
include ../rules.mk

# For post synth simulation:
#  * make synth
#  * comment the below line
#  * make
#  * make hello_LTC_view
SRC_V += $(SIM_PATH)/glbl.v

all:
	$(TARGETS).bit

synth:
	python3 $(TARGETS).py synth

config:
	python3 $(TARGETS).py config

clean::
	rm -rf build mem.init

