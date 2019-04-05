# SP605 USB JTAG
The SP605 on-board JTAG interface needs a special driver which uploads the firmware and initializes the usb-chip.
It then re-enumerates as a device which xc3sprog can speak to. Here's how I installed it on debian.

```bash
sudo apt install libusb-1.0-0 libusb-1.0-0-dev fxload
sudo cp /opt/Xilinx/14.7/ISE_DS/ISE/bin/lin64/*.hex /usr/share
sudo cp /opt/Xilinx/14.7/ISE_DS/ISE/bin/lin64/xusbdfwu.rules /etc/udev/rules.d
sudo sed -i -e 's/TEMPNODE/tempnode/' -e 's/SYSFS/ATTRS/g' -e 's/BUS/SUBSYSTEMS/' /etc/udev/rules.d/xusbdfwu.rules
# Plug in the jtag usb
lsusb
# Bus 004 Device 018: ID 03fd:0008 Xilinx, Inc. Platform Cable USB II
```

Then install xc3sprog and use `xpc` cable
