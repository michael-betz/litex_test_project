`timescale 1 ns / 1 ps

module IserdesSp6_tb;
    `include "test/sp6_tb_common.v"
    initial
        if ($test$plusargs("vcd")) begin
            $dumpfile("sp6_ddr.vcd");
            $dumpvars(5, IserdesSp6_tb);
        end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    top dut (
        .reset          (reset),
        .dco_p          (dco_clk_p),
        .dco_n          (~dco_clk_p),
        // .lvds_data_p    ({out_b_p, out_a_p}),
        // .lvds_data_n    ({~out_b_p, ~out_a_p}),
        .lvds_data_p    (out_a_p),
        .lvds_data_n    (~out_a_p),
        .data_outs      (data_outs),
        .bitslip        (bitslip),
        .sample_clk     (sample_clk),
        .pd_int_period  (32'd64),
        .id_auto_control(1'b1),
        .id_mux         (1'b0),
        .id_inc         (1'b0),
        .id_dec         (1'b0)
    );

endmodule
