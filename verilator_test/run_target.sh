#!/bin/bash
set -e
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
if [[ $# -ne 1 ]]; then
    echo "to run the soc simulation demo target, try: $ $0 soc"
    exit 2
fi

if [[ sim_$1.py -nt out/gateware/build_sim.sh ]]; then
	# rebuild emulator if it is out of date / doesn't exist
	rm -rf out
	# --trace
	python3 sim_$1.py
	(cd out/gateware &&	source build_sim.sh)
fi

# run the emulator
cd out/gateware
./obj_dir/Vsim &

# connect to emulator, run the client application
cd ../..
# --debug
litex_server --uart --uart-port socket://localhost:1111 &
sleep 0.2
python3 test_$1.py

# rude way of stopping the emulator
pkill Vsim
