# verilator + litex_server experiment

Connect to a piece of emulated hardware (verilator simulation)
in the same way as connecting to real hardware.

I mostly use this test-setup to troubleshoot and experiment with litex socs, to gain a better understanding of how they work under the hood.

## the setup

  * Add the serial2tcp plugin to verilator such that I can connect to the SOC UART
    from outside
  * Run litex_server to connect to the tcp socket instead to a serial port
    such that I can access the emulated wishbone bus from outside

## to run the simulation

```bash
# all 3 run at the same time in separate windows ...
$ python3 sim_soc.py
$ litex_server --uart --uart-port socket://localhost:1111
$ python3 test_soc.py
Connected to Port 1234
LiteX Simulation 2019-07-31 19:58:51
```
The last line is a string read out from ID memory on the virtual hardware.

alternatively, use the provided script
```bash
$ ./run_target.sh soc
```

## gotchas

Turns out there's a hardware timeout in the litex uart_to_wishbone_bridge, for which litex calculates the number of cycles at build time based on the configured _system clock frequency_. For the Verilator simulation it depends on CPU speed and is not accurately known in advance.
If there's hangs in the litex_server communication, try setting `sys_clk_freq` to a __larger__ value, which will make the timeout expire later.
