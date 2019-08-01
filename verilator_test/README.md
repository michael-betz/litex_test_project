# verilator + litex_server experiment

I want to connect to a piece of emulated hardware (through verilator)
in the same way as I would connect to real hardware.

## steps to get there

  * Add the serial2tcp plugin to verilator such that I can connect to the SOC UART
    from outside
  * Run litex_server to connect to the tcp socket instead to a serial port
    such that I can access the emulated wishbone bus from outside

## steps which got me there

```bash
# all 3 run at the same time in separate windows ...
$ python3 verilator_sim.py
$ litex_server --uart --uart-port socket://localhost:1111
$ python3 test.py
Connected to Port 1234
LiteX Simulation 2019-07-31 19:58:51
```
The last line is a string read out from ID memory on the virtual hardware.

## gotchas

Turns out there's a hardware timeout in the litex uart_to_wishbone_bridge, for which litex calculates the number of cycles at build time based on the configured _system clock frequency_. For the Verilator simulation it depends on CPU speed and is not accurately known in advance.
If there's hangs in the litex_server communication, try setting `sys_clk_freq` to a __larger__ value, which will make the timeout expire later.
