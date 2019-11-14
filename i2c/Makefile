TARGET = i2c

%.v: %.py
	python3 $< build

%.vcd: %_tb
	vvp -N $< +vcd

%_tb: %_tb.v %.v
	# Add -pfileline=1 for simulation tracing
	iverilog -o $@ $^ 

all: $(TARGET).vcd

clean:
	rm -rf $(TARGET).vcd $(TARGET)_tb $(TARGET).v mem_1.init
