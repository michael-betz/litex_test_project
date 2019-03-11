BUILD_DIR=../build

include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

TARGET   = boot
OBJECTS  = isr.o main.o
LDFLAGS += --no-relax --print-memory-usage

CRT_O = $(BUILD_DIR)/software/libbase/crt0-$(CPU)-
ifeq ($(EXECUTE_IN_PLACE),1)
	CRT_O :=$(CRT_O)xip.o
else
	CRT_O :=$(CRT_O)ctr.o
endif

all: $(TARGET).bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

$(TARGET).elf: $(OBJECTS)
	$(LD) $(LDFLAGS) \
		-T linker.ld \
		-N -o $@ \
		$(CRT_O) \
		$(OBJECTS) \
		-L$(BUILD_DIR)/software/libbase \
		-L$(BUILD_DIR)/software/libcompiler_rt \
		-lbase-nofloat -lcompiler_rt
	chmod -x $@


%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif
ifeq ($(CPUENDIANNESS),little)
	$(PYTHON) -m litex.soc.tools.mkmscimg $@ --little
else
	$(PYTHON) -m litex.soc.tools.mkmscimg $@
endif

%.lst: %.elf
	riscv32-unknown-elf-objdump -d $^ > $@

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) $(TARGET).elf $(TARGET).bin $(TARGET).lst .*~ *~

.PHONY: all clean
