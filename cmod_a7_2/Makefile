BUILD_FOLDER = build
TOP_PY  = cmod_a7_design_example.py
TOP_V   = $(BUILD_FOLDER)/gateware/top.v
TOP_BIT = $(BUILD_FOLDER)/gateware/top.bit
COMMON_OPTS = --output-dir $(BUILD_FOLDER) \
			  --csr-csv $(BUILD_FOLDER)/csr.csv \
			  --cpu-type picorv32

all: clean $(TOP_V)

$(TOP_V):
	python3 $(TOP_PY) $(COMMON_OPTS) --no-compile-gateware

$(TOP_BIT):
	python3 $(TOP_PY) $(COMMON_OPTS)

config: $(TOP_BIT)
	python3 -c "import cmod_a7;\
	 cmod_a7.Platform().create_programmer().load_bitstream('$^')"

firmware/boot.bin:
	make -C firmware all

# build the emulator
build/gateware/obj_dir/Vdut:
	python3 cmod_a7_sim.py $(COMMON_OPTS)
	(cd ./build/gateware/; sh build_dut.sh)

# start the emulator
semu: build/gateware/obj_dir/Vdut
	(cd ./build/gateware/; obj_dir/Vdut)

term: firmware/boot.bin
	litex_term --serial-boot --make --kernel $^ socket://localhost:55555

test:
	-pkill litex_server*
	litex_server uart /dev/ttyUSB1 115200&
	ipython --pylab -i test.py

clean:
	rm -rf $(BUILD_FOLDER)
	rm -f *.vcd

.PHONY: clean config test sim all semu term
