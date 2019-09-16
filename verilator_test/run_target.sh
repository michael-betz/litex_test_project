#!/bin/bash
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT
if [[ $# -ne 1 ]]; then
    echo "to run the soc simulation demo target, try: $ $0 soc"
    exit 2
fi
python3 sim_$1.py #--trace
cd out/gateware
source build_dut.sh
./obj_dir/Vdut &
cd ../..
litex_server --uart --uart-port socket://localhost:1111 &
sleep 0.5
python3 test_$1.py
