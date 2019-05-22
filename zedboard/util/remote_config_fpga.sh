#!/bin/bash
# Usage: config_remote.sh bitfile.bit.bin
# Requires ssh-login with pre-shared key and sudo without password :p
HOSTNAME=spaetzle.dhcp
FILE_NAME=$(basename -- "$1")
scp $1 $HOSTNAME:
ssh $HOSTNAME "set -e; sudo cp -f $FILE_NAME /lib/firmware; echo $FILE_NAME | sudo tee /sys/class/fpga_manager/fpga0/firmware; dmesg | tail -n 1"
