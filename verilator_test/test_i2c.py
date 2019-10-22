'''
Test and explore litex I2C bit-banging core
'''
from litex import RemoteClient

def main():
    port = 1234
    r = RemoteClient(csr_csv='out/csr.csv', debug=False, port=port)
    r.open()
    print("Connected to Port", port)

    def SDAR():
        return r.regs.dut_i2c_master_r.read()

    # This should print `1`!  (see verilator_sim.py:59)
    print(SDAR())

    # I2C_W_SCL = 0
    # I2C_W_OE  = 1
    # I2C_W_SDA = 2
    # I2C_R_SDA = 0
    # for i in range(5, 30):
    #     r.regs.dut_i2c_master_w.write(i)
    #     print(r.regs.dut_i2c_master_w.read())
    # print('i2c:', r.regs.dut_i2c_master_w.read())
    # print("dut_status: 0x{:02x}".format(r.regs.dut_status_test.read()))
    # print(getId(r))


if __name__ == "__main__":
    main()