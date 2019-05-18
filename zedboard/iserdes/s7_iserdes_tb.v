`timescale 1 ns / 1 ps

module s7_iserdes_tb;
    `include "../../sp605/iserdes/test/sp6_tb_common.v"
    initial
        if ($test$plusargs("vcd")) begin
            $dumpfile("s7_iserdes.vcd");
            $dumpvars(5, s7_iserdes_tb);
        end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    s7_iserdes dut (
        .dco_p          (dco_clk_p),
        .dco_n          (~dco_clk_p),
        .lvds_data_p    (out_a_p),
        .lvds_data_n    (~out_a_p),
        .sys_clk        (sys_clk),
        .sys_rst        (reset),
        .id_inc         (1'b0),
        .id_dec         (1'b0),
        .id_value       (),
        .bitslip        (1'b0),
        .data_outs      ()
    );

endmodule
