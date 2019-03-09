BUILD_FOLDER = build
TOP_PY  = cmod_a7_design_example.py
TOP_V   = $(BUILD_FOLDER)/gateware/top.v
TOP_BIT = $(BUILD_FOLDER)/gateware/top.bit
COMMON_OPTS = --output-dir $(BUILD_FOLDER) --csr-csv $(BUILD_FOLDER)/csr.csv

all: clean $(TOP_V)

$(TOP_V):
	python3 $(TOP_PY) $(COMMON_OPTS) --no-compile-gateware

$(TOP_BIT):
	python3 $(TOP_PY) $(COMMON_OPTS)

config: $(TOP_BIT)
	python3 -c "import cmod_a7;\
	 cmod_a7.Platform().create_programmer().load_bitstream('$^')"

test:
	-pkill litex_server*
	litex_server uart /dev/ttyUSB1 115200&
	ipython --pylab -i test.py

clean:
	rm -rf $(BUILD_FOLDER)
	rm -f *.vcd

.PHONY: clean config test all
