from litex import RemoteClient

def getId(r):
    s = ""
    for i in range(64):
        temp = r.read(r.bases.identifier_mem + i * 4)
        if temp == 0:
            break
        s += chr(temp & 0xFF)
    return s


def main():
    port = 1234
    r = RemoteClient(csr_csv='csr.csv', debug=False, port=port)
    r.open()
    print("Connected to Port", port)
    print(getId(r))
    print("dut_status: 0x{:02x}".format(r.regs.dut_status_test.read()))


if __name__ == "__main__":
    main()
