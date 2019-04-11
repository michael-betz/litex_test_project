TARGETS = hello_ETH
include ../rules.mk

# For post synth simulation:
#  * make synth
#  * comment the below line
#  * make
#  * make hello_ETH_view
SRC_V += $(SIM_PATH)/glbl.v

synth:
	python3 $(TARGETS).py synth

config:
	python3 $(TARGETS).py config

clean::
	rm -rf build mem.init

