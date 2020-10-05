'''
Test and explore litex I2C bit-banging core
'''
from litex import RemoteClient
import sys
sys.path.append('..')
from common import getId
from time import sleep


def main():
    port = 1234
    r = RemoteClient(csr_csv='out/csr.csv', debug=False, port=port)
    r.open()
    print("Connected to Port", port)
    print(getId(r))

    def SDAR():
        return r.regs.i2c_master_r.read()

    # This should print `1`!  (see verilator_sim.py:59)
    print(SDAR())

    # I2C_W_SCL = 0
    # I2C_W_OE  = 1
    # I2C_W_SDA = 2
    # I2C_R_SDA = 0
    for i in range(5, 30):
        r.regs.i2c_master_w.write(i)
        print(r.regs.i2c_master_w.read())


if __name__ == "__main__":
    main()
