VIVADO_SIM = /opt/Xilinx/Vivado/2018.3/data/verilog/src
LITE_ETH = ~/fpga_wsp/litex/liteeth/examples
SIM_INCLUDES = -y . -y $(VIVADO_SIM)/unisims
TARGET = basesoc_kc705

all: $(TARGET).vcd

%.vcd: %_tb
	vvp -N $<

%_tb: %_tb.v %.v
	iverilog $(SIM_INCLUDES) -pfileline=1 -o $@ $< $(VIVADO_SIM)/glbl.v

basesoc_kc705.v:
	(cd $(LITE_ETH); python3 make.py -t base -s BaseSoC -p kc705 -Ob run False build-bitstream)
	cp $(LITE_ETH)/build/$@ .
	cp $(LITE_ETH)/build/mem_1.init .

clean:
	rm -rf $(TARGET).vcd $(TARGET)_tb $(TARGET).v mem_1.init
