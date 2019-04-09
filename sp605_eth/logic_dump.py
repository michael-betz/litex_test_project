#!/usr/bin/env python3

from litex import RemoteClient
from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver

for i in range(32):
    try:
        wb = RemoteClient(csr_csv="build/csr.csv", debug=False, port=1234 + i)
        wb.open()
        print("Connected to Port", 1234 + i)
        break
    except Exception:
        pass

analyzer = LiteScopeAnalyzerDriver(
    wb.regs, "analyzer", config_csv="build/analyzer.csv", debug=True
)
analyzer.configure_trigger(cond={})
analyzer.configure_subsampler(1)
analyzer.run(offset=128, length=256)
analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

wb.close()
