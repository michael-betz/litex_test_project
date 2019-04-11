`timescale 1 ns / 1 ps

module sp6_pll_tb;
    `include "test/sp6_tb_common.v"
    initial
        if ($test$plusargs("vcd")) begin
            $dumpfile("sp6_pll.vcd");
            $dumpvars(5, sp6_pll_tb);
        end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    sp6_pll dut (
        .reset          (reset),
        .dco_p          (fr_clk),
        .dco_n          (~fr_clk),
        // .lvds_data_p    ({out_b_p, out_a_p}),
        // .lvds_data_n    ({~out_b_p, ~out_a_p}),
        .lvds_data_p    (out_a_p),
        .lvds_data_n    (~out_a_p),
        .data_outs      (data_outs),
        .clk_data_out   (clk_data_out),
        .bitslip        (bitslip),
        .sample_clk     (sample_clk),
        .pd_int_period  (32'd64),
        .id_auto_control(1'b1),
        .id_mux         (1'b0),
        .id_inc         (1'b0),
        .id_dec         (1'b0)
    );

    // initial
    //     bitslip_task(3);

    always @(posedge sample_clk)
        if ((cc > 150) && (clk_data_out != 8'h0F))
            pass = 0;

endmodule
