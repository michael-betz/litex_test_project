# Litex example project

My testbed for getting the picorv32 CPU running on a cmodA7 board and learning about litex in the progress.

# Install litex
```bash
git clone --recurse-submodules https://github.com/yetifrisstlama/litex.git
cd litex
python litex_setup.py init
python litex_setup.py install
patch litex/soc/cores/cpu/picorv32/verilog/picorv32.v picorv32.v.patch
```

# Install openocd
```bash
sudo apt-get install libusb-1.0-0-dev
git clone --recurse-submodules git://repo.or.cz/openocd.git

# git clone https://github.com/SpinalHDL/openocd_riscv.git
# wget https://raw.githubusercontent.com/m-labs/VexRiscv-verilog/master/cpu0.yaml

cd openocd/
./bootstrap
./configure --enable-ftdi --enable-dummy
make -j4
sudo make install
sudo cp ./contrib/60-openocd.rules /etc/udev/rules.d/
sudo cp digilent_cmod_a7.cfg /usr/local/share/openocd/scripts/board/
```

# Install risc-v toolchain
```bash
git clone --recurse-submodules https://github.com/riscv/riscv-gnu-toolchain
cd riscv-gnu-toolchain/
sudo mkdir /opt/riscv32im
sudo chown $USER /opt/riscv32im
./configure --prefix=/opt/riscv32im --with-arch=rv32im
make -j4
# get some coffee ...
```

... and this is what I have in my `.bashrc` right now
```bash
# added by Miniconda3 installer
export PATH="/home/michael/miniconda3/bin:$PATH"
# Vivado / FPGA stuff
export PATH="/opt/Xilinx/Vivado/2018.2/bin:$PATH"
export PATH="/opt/riscv32im/bin:$PATH"

```

# Workflow
Synthesize, build firmware, configure fpga, connect to UART terminal, load user-app, hack:
```bash
python base_cpu.py build    # Synthesize
python base_cpu.py config   # Load .bit file into fpga
litex_term --kernel firmware/firmware.bin --make /dev/ttyUSB1
```
Pressing Btn0 should reset the soc, trigger a `make all` and reload the new firmware.
