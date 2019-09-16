'''
Demonstrate the connection to verilator. In particular:
    test_soc.py <--> litex_server <--> serial2tcp <--> Emulated SimSoc (Verilator)

do that by reading the device identifier memory. Script should output something like:
    Connected to Port 1234
    LiteX Simulation 2019-09-15 21:31:41

run it like this:
    $ python3 sim_soc.py
    $ litex_server --uart --uart-port socket://localhost:1111
    $ python3 test_soc.py

or just:
    $ make test_soc.vcd
'''
import sys
sys.path.append('..')
from common import conLitexServer


r = conLitexServer(csr_csv='out/csr.csv', port=1234)
