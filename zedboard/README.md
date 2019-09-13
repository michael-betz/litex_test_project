# Steps to get debian running on zedboard
It's like having a raspberry pi in your FPGA :)

mostly based on these two guides:
  * https://github.com/PyHDI/zynq-linux
  * https://blog.n621.de/2016/05/running-linux-on-a-zynq-without-vivado-madness/

## Bootloaders
```bash
# Cross compiler
    sudo apt install libc6-armel-cross libc6-dev-armel-cross binutils-arm-linux-gnueabi libncurses-dev
    sudo apt-get install gcc-arm-linux-gnueabi g++-arm-linux-gnueabi libssl-dev
    export CROSS_COMPILE=arm-linux-gnueabi-
    export ARCH=arm

# compile U-Boot
    git clone https://github.com/Xilinx/u-boot-xlnx.git --recursive
    cd u-boot-xlnx/
    make zynq_zed_defconfig
    make menuconfig
    make
    export PATH=$PATH:/<..>/u-boot-xlnx/tools/

# Create a ~ 32 MB FAT16 partition on the SD card,
# follow the guide below or use gparted
# in this example it's mounted as /media/sdcard

# Copy first stage bootloader and u-boot image to SD card
    cp u-boot-xlnx/spl/boot.bin /media/sdcard
    cp u-boot-xlnx/u-boot.img /media/sdcard

# Now try it on the Zedboard, you should see u-boot starting on the UART

# compile Kernel
    git clone https://github.com/Xilinx/linux-xlnx.git --recursive
    cd linux-xlnx/
    make xilinx_zynq_defconfig
    make menuconfig
    make -j4 uImage LOADADDR=0x00008000
    make zynq-zed.dtb

# Copy kernel image and device-tree to SD card
    cp arch/arm/boot/uImage /media/sdcard/
    cp arch/arm/boot/dts/zynq-zed.dtb /media/sdcard

# to configure u-boot, create a uEnv.txt as shown below and copy it to SD card

# Try it on Zedboard, the linux kernel should boot and panic
# because of the missing root filesystem
```

## Debian `rootfs`
setup your initial bare-bones debian environment using chroot on the host.
```bash
# debian rootfs (on host)
    sudo apt install debootstrap qemu-user-static
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
    apt upgrade
    apt install openssh-server ntp sudo
    passwd
    adduser <user_name>
    visudo

root        ALL=(ALL:ALL) ALL
<user_name> ALL=(ALL:ALL) ALL

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

# Mount fat16 boot partition for kernel updates / uboot config
    mkdir /boot  # only if it does not exist already
    vim /etc/fstab

/dev/mmcblk0p1 /boot auto defaults 0 0

# Optional Hack to get cross-compiled binaries to run
    sudo ln -s /lib/arm-linux-gnueabihf/ld-2.24.so /lib/ld-linux.so.3

# Exit the chroot shell

# Create a large ext4 partition on the SD card (see below)
# in this example it is mounted as /media/rootfs
    sudo cp -rp rootfs/* /media/rootfs

# The zedboard should boot into linux
# and there should be a login prompt on the UART
```

# Partitioning the SD card
What we need

  * FAT16 partition of size 32 MB
  * Linux (ext4) over the remaining available space

Using `fdisk` on a 2 GB SD card, it should look like this:
```
Device     Boot Start     End Sectors  Size Id Type
/dev/sdd1        2048   67583   65536   32M  e W95 FAT16
/dev/sdd2       67584 3842047 3774464  1.8G 83 Linux
```

then format the partitions as FAT16 and ext4:

```bash
sudo mkfs.vfat -F16 -v /dev/sdd1 -n boot
sudo mkfs.ext4 -v /dev/sdd2 -L rootfs
```

__make sure to replace `sdd1` and `sdd2` with the actual partition names__

# uEnv.txt
U-Boot startup script to boot and optionally load a bitfile. Make sure `ethaddr` is unique on network.
```bash
# fpga_addr=0x10000000
# fpga_load=load mmc 0 ${fpga_addr} zed_wrapper.bit
# fpga_boot=fpga loadb 0 ${fpga_addr} $filesize

kernel_addr=0x8000
kernel_load=load mmc 0 ${kernel_addr} uImage

dtr_addr=0x100
dtr_load=load mmc 0 ${dtr_addr} zynq-zed.dtb

kernel_boot=setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait; bootm ${kernel_addr} - ${dtr_addr}

# to load bitfile before boot, uncomment the above 3 lies
# and add this to beginning: run fpga_load; run fpga_boot;
bootcmd=run kernel_load; run dtr_load; setenv ethaddr 00:0a:35:00:01:87; run kernel_boot
```

# Load bitfile in linux
Bitfiles are loaded trough the [Linux FPGA Manager](https://www.kernel.org/doc/html/v4.18/driver-api/fpga/fpga-mgr.html).
For this to work, the .bit file needs its header removed and its bytes swapped. There's two ways to do that:

## bootgen
prepare `<bitfile>.bit.bin` with bootgen. Unfortunately needs xilinx SDK.

```bash
    cat <bitfile>.bif

all:
{
        <bitfile>.bit
}

    bootgen -image <bitfile>.bif -arch zynq -process_bitstream bin
```

## alternatively: bitstream_fix.py
does not need xilinx SDK
```bash
python3 util/bitstream_fix.py <bitfile>.bit
```

copy the resulting `<bitfile>.bit.bin` on the zedboard, then

```bash
    sudo -i
    cp <bitfile>.bit.bin /lib/firmware/
    echo 0 > /sys/class/fpga_manager/fpga0/flags
    echo <bitfile>.bit.bin > /sys/class/fpga_manager/fpga0/firmware
    dmesg

[ 1667.020520] fpga_manager fpga0: writing <bitfile>.bit.bin to Xilinx Zynq FPGA Manager
```

`make upload` automates all these steps.

# how to get `ip/processing_system7_0.xci`
This Xilinx IP file contains the PS7 block describing the connectivity between PS and PL and is required by the Litex `SoCZynq()` class. If the PS7 block is not included in the PL design, the CPU will freeze as soon as the the resulting bitfile is loaded on the zedboard. However, except for the CPU freezing issue, the PL part of the design seems to work fine.

  1. open vivado, new RTL project, `zedboard` hardware platform, don't add source files, next, next next ..
  2. open IP manager, add Zynq Processing system 7 IP
  3. configure it in GUI, Bank0 / 1 voltage = 2.5 V, clock0 100 MHz. By default, clock0 is connected to litex `sysclk`.
  4. Save and close
  5. `zed/zed.srcs/sources_1/ip/processing_system7_0/processing_system7_0.xci`

# remote litex_server
`./litex_server` contains a minimal version of which can run on the zedboard. It only requires python3 installed. It needs sudo to open `/dev/mem`, so it is dangerous! It then connects to the general purpose AXI master (gp0) at address 0x43c00000. On the PL side, this is connected to an AXI to Wishbone converter to read and write the CSRs.

## GP0 address range
The Zynq general purpose AXI master interfaces are mapped to these addresses in memory

| Start     | End      | Size               | Interface |
| --------- | -------- | ------------------ | --------- |
| 4000_0000 | 7FFF_FFF | 3800_0000 (896 MB) | M_AXI_GP0 |
| 8000_0000 | BFFF_FFF | 3800_0000 (896 MB) | M_AXI_GP1 |

The AXI to wishbone adapter subtracts an offset (base_address) and removes the 2 LSB bits so we get word addresses.
See mapping below.

```python
self.add_axi_to_wishbone(self.axi_gp0, base_address=0x4000_0000)
```

| AXI (devmem) | WB << 2     | WB           |
| ------------ | ----------- | ------------ |
| 0x4000_0000  | 0x0000_0000 | 0x0000_0000  |
| 0x4000_0004  | 0x0000_0004 | 0x0000_0001  |
| 0x7FFF_FFFC  | 0x3FFF_FFFC | 0x0FFF_FFFF  |
