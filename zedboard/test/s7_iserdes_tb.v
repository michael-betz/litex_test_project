`timescale 1 ns / 1 ps

module s7_iserdes_tb;
    `include "../sp605/iserdes/test/sp6_tb_common.v"
    initial
        if ($test$plusargs("vcd")) begin
            $dumpfile("s7_iserdes.vcd");
            $dumpvars(5, s7_iserdes_tb);
        end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    s7_iserdes dut (
        .rx_p           (dco_clk_p),
        .rx_n           (~dco_clk_p),
        .data_delayed   (),
        .sys_clk        (sys_clk),
        .sys_rst        (1'b0)
    );

endmodule
