# SP605 USB JTAG
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
