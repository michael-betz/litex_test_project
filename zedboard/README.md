# Steps to get debian running on zedboard
mostly based on (https://github.com/PyHDI/zynq-linux).

```bash
# Cross compiler
    sudo apt install libc6-armel-cross libc6-dev-armel-cross binutils-arm-linux-gnueabi libncurses-dev
    sudo apt-get install gcc-arm-linux-gnueabi g++-arm-linux-gnueabi
    export CROSS_COMPILE=arm-linux-gnueabi-
    export ARCH=arm

# compile U-Boot
    git clone https://github.com/Xilinx/u-boot-xlnx.git --recursive
    cd u-boot-xlnx/
    make zynq_zed_defconfig
    make menuconfig
    make
    export PATH=$PATH:/<..>/u-boot-xlnx/tools/

# compile Kernel
    git clone https://github.com/Xilinx/linux-xlnx.git --recursive
    cd linux-xlnx/
    make xilinx_zynq_defconfig
    make menuconfig
    make -j4 uImage LOADADDR=0x00008000
    make zynq-zed.dtb
    cp arch/arm/boot/uImage /media/sdcard/
    cp arch/arm/boot/dts/zynq-zed.dtb /media/sdcard

# debian rootfs (on host)
    mkdir rootfs
    sudo debootstrap --arch=armhf --foreign stretch rootfs
    sudo cp /usr/bin/qemu-arm-static rootfs/usr/bin/
    sudo chroot rootfs/

# debian rootfs (chroot)
    distro=stretch
    export LANG=C
    debootstrap/debootstrap --second-stage
    vim /etc/apt/sources.list

deb http://deb.debian.org/debian stretch main
deb http://deb.debian.org/debian-security/ stretch/updates main
deb http://deb.debian.org/debian stretch-updates main

    apt update
    apt install locales dialog
    passwd
    apt upgrade
    adduser <user_name>
    visudo

root        ALL=(ALL:ALL) ALL
<user_name> ALL=(ALL:ALL) ALL

    dpkg-reconfigure locales

C.UTF8

    apt install openssh-server ntp sudo python3
    vim /etc/network/interfaces

allow-hotplug eth0
iface eth0 inet dhcp

    vim /etc/hostname

<hostname>

    vim /etc/hosts

127.0.0.1   localhost <hostname>
::1     localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters

# Mount fat32 boot partition for kernel updates / uboot config
    mkdir boot
    vim /etc/fstab

/dev/mmcblk0p1 /boot auto defaults 0 0

# I needed that to get cross-compiled binaries to run
    sudo ln -s /lib/arm-linux-gnueabihf/ld-2.24.so /lib/ld-linux.so.3
```

# uEnv.txt
U-Boot startup script to boot and load bitfile. Make sure `ethaddr` is unique on network.
```bash
fpga_addr=0x10000000
fpga_load=load mmc 0 ${fpga_addr} zed_wrapper.bit
fpga_boot=fpga loadb 0 ${fpga_addr} $filesize

kernel_addr=0x8000
kernel_load=load mmc 0 ${kernel_addr} uImage

dtr_addr=0x100
dtr_load=load mmc 0 ${dtr_addr} zynq-zed.dtb

kernel_boot=setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait; bootm ${kernel_addr} - ${dtr_addr}

# to load bitfile before boot, add this to beginning: run fpga_load; run fpga_boot;
bootcmd=run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:01:87; run kernel_boot
```

# Load bitfile in linux
prepare `zed_wrapper.bit.bin` with bootgen. Unfortunately needs xilinx SDK.

```bash
    cat zed_wrapper.bif

all:
{
        zed_wrapper.bit
}

    bootgen -image zed_wrapper.bif -arch zynq -process_bitstream bin
```

[zynq-mkbootimage](https://github.com/antmicro/zynq-mkbootimage/issues/10) seems to be an -- not quite yet fully implemented -- alternative.

Update: this one does the job just fine: [bitstream_fix.py](https://github.com/peteut/migen-axi/blob/master/src/tools/bitstream_fix.py) No need for .bif or to install xilinx SDK!

copy `.bit.bin` on the zedboard, then

```bash
    sudo -i
    cp zed_wrapper.bit.bin /lib/firmware/
    echo 0 > /sys/class/fpga_manager/fpga0/flags
    echo zed_wrapper.bit.bin > /sys/class/fpga_manager/fpga0/firmware
    dmesg

[ 1667.020520] fpga_manager fpga0: writing zed_wrapper.bit.bin to Xilinx Zynq FPGA Manager
```

`make upload` automates all these steps.

# how to get `ip/processing_system7_0.xci`
  1. open vivado, new RTL project `zed`, don't add source files, next, next next ..
  2. open IP manager, add Zynq Processing system 7 IP
  3. configure it in GUI, Bank0 / 1 voltage = 2.5 V, clock0 100 MHz
  4. Save and close
  5. `zed/zed.srcs/sources_1/ip/processing_system7_0/processing_system7_0.xci`

# remote litex_server
`./litex_server` contains a minimal version of which can run on the zedboard. It only requires python3 installed. It needs sudo to open `/dev/mem`, so it is dangerous! It then connects to the general purpose AXI master (gp0) at address 0x43c00000. On the PL side, this is connected to an AXI to Wishbone converter to read and write the CSRs.
