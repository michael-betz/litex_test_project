`timescale 1 ns / 1 ps

module iserdes_tb;
    localparam real SYS_CLK_PERIOD = 1e9 / 100e6;    // Simulated clock period in [ns]
    localparam real FR_CLK_PERIOD = 1e9 / 125e6;
    localparam real DCO_CLK_PERIOD = FR_CLK_PERIOD / 8.0;
    // Clock generation
    reg sys_clk = 1;
    reg fr_clk = 1;
    reg dco_clk_p = 0;
    reg out_a_p = 0;
    always #(SYS_CLK_PERIOD / 2) sys_clk = ~sys_clk;
    always #(FR_CLK_PERIOD / 2) fr_clk = ~fr_clk;
    initial begin
        #(DCO_CLK_PERIOD / 4.1);
        forever #(DCO_CLK_PERIOD / 2) dco_clk_p = ~dco_clk_p;
    end
    always begin
        // Craft an 8 bit DDR signal 0b00000010
        out_a_p = 0;
        #(DCO_CLK_PERIOD / 2.0);
        #(DCO_CLK_PERIOD / 2.0);
        #(DCO_CLK_PERIOD / 2.0);
        #(DCO_CLK_PERIOD / 2.0);
        #(DCO_CLK_PERIOD / 2.0);
        #(DCO_CLK_PERIOD / 2.0);
        out_a_p = 1;
        #(DCO_CLK_PERIOD / 2.0);
        out_a_p = 0;
        #(DCO_CLK_PERIOD / 2.0);
    end

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("iserdes.vcd");
            $dumpvars(5,iserdes_tb);
        end
        repeat (3) @(posedge sys_clk);
        reset <= 0;
        #20000
        $finish();
    end
    integer cc = 0;
    always @(posedge sys_clk) cc <= cc + 1;

reg serdes_clk_rst = 0;
wire rxioclkp, rxioclkn, rx_serdesstrobe;
serdes_1_to_n_clk_ddr_s8_diff #(
    .S              (8)
) serdec_clk (
    .clkin_p        (dco_clk_p),
    .clkin_n        (~dco_clk_p),
    .rxioclkp       (rxioclkp),
    .rxioclkn       (rxioclkn),
    .rx_serdesstrobe(rx_serdesstrobe),
    .rx_bufg_x1     ()
);

wire [7:0] data_out;
wire [7:0] frame_out;
serdes_1_to_n_data_ddr_s8_diff #(
    .S              (8),
    .D              (2)
) serdes_dat_0 (
    .use_phase_detector(1'b1),
    .datain_p       ({fr_clk, out_a_p}),
    .datain_n       ({~fr_clk, ~out_a_p}),
    .rxioclkp       (rxioclkp),
    .rxioclkn       (rxioclkn),
    .rxserdesstrobe (rx_serdesstrobe),
    .reset          (reset),
    .gclk           (sys_clk),
    .bitslip        (1'b0),
    .data_out       ({frame_out, data_out}),
    .debug_in       (),
    .debug          ()
);

// always @(posedge sys_clk) begin
//     serdes_clk_rst <= 0;
//     if (cc == 30) serdes_clk_rst <= 1;
// end

endmodule
