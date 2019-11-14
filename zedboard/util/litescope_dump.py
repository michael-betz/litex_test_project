#!/usr/bin/env python3
from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver
import sys


# -----------------------
#  litex_server stuff
# -----------------------
def getId(r):
    s = ""
    for i in range(64):
        temp = r.read(r.bases.identifier_mem + i * 4)
        if temp == 0:
            break
        s += chr(temp & 0xFF)
    return s


def conLitexServer(csr_csv="build/csr.csv", port=1234):
    for i in range(32):
        try:
            r = RemoteClient(csr_csv=csr_csv, debug=False, port=port + i)
            r.open()
            print("Connected to Port", 1234 + i)
            break
        except ConnectionRefusedError:
            r = None
    if r:
        print(getId(r))
    else:
        print("Could not connect to RemoteClient")
    return r


r = conLitexServer("csr.csv")

# # #

analyzer = LiteScopeAnalyzerDriver(
    r.regs,
    "analyzer",
    config_csv="analyzer.csv",
    debug=True
)
analyzer.configure_subsampler(1)
analyzer.configure_group(0)
try:
    trig = sys.argv[1]
except Exception:
    trig = "user_btn_u"
print("Trigger:", trig)
analyzer.add_rising_edge_trigger(trig)
analyzer.run(offset=32, length=4095)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

# # #

r.close()
