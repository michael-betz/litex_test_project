`timescale 1 ns / 1 ps

module iserdes_tb;
    localparam real SYS_CLK_PERIOD = 1e9 / 100e6;    // Simulated clock period in [ns]
    localparam real FR_CLK_PERIOD = 1e9 / 125e6 * 2; // DDR !
    localparam real DCO_CLK_PERIOD = FR_CLK_PERIOD / 8.0; // DDR
    // Clock generation
    reg sys_clk = 1;
    reg fr_clk = 1;
    reg dco_clk_p = 0;
    reg out_a_p = 0;
    reg out_b_p = 0;
    always #(SYS_CLK_PERIOD / 2) sys_clk = ~sys_clk;
    always #(FR_CLK_PERIOD / 2) fr_clk = ~fr_clk;
    initial begin
        #(DCO_CLK_PERIOD / 4.2);
        forever #(DCO_CLK_PERIOD / 2) dco_clk_p = ~dco_clk_p;
    end
    // reg [15:0] testPattern = 16'b1110000000000010;
    reg [15:0] testPattern = 16'b0000000000001101;
    reg [15:0] temp = 0;

    always begin
        // Craft 2 x 8 bit DDR signals according to timing diagram in LTC datasheet
        temp = testPattern;
        repeat (8) begin
            out_a_p = (temp & 16'h8000) != 0;
            temp = temp << 1;
            out_b_p = (temp & 16'h8000) != 0;
            temp = temp << 1;
            #(DCO_CLK_PERIOD / 2.0);
        end
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
        #5000
        $finish();
    end
    integer cc = 0;
    always @(posedge sys_clk) cc <= cc + 1;

wire rxioclk, rx_serdesstrobe, sample_clk;
serdes_1_to_n_clk_pll_s8_diff #(
    .S              (8),
    .PLLX           (2),
    .CLKIN_PERIOD   (DCO_CLK_PERIOD),
    .BS             ("FALSE")
) serdec_clk (
    .clkin_p        (dco_clk_p),
    .clkin_n        (~dco_clk_p),
    .reset          (reset),
    .pattern1       (8'h00),
    .pattern2       (8'hFF),
    .rxioclk        (rxioclk),
    .rx_serdesstrobe(rx_serdesstrobe),
    .bitslip        (),
    .rx_bufg_pll_x1 (sample_clk)
);

wire [23:0]data_out;
wire [7:0] data_out_a;
wire [7:0] data_out_b;
wire [7:0] frame_out;
wire signed [8:0] del_a, del_b, del_fr;
reg bitslip=0;
serdes_1_to_n_data_s8_diff #(
    .S              (8),
    .D              (3)
) serdes_dat_0 (
    .use_phase_detector(1'b1),
    .datain_p       ({fr_clk, out_b_p, out_a_p}),
    .datain_n       ({~fr_clk, ~out_b_p, ~out_a_p}),
    .rxioclk        (rxioclk),
    .rxserdesstrobe (rx_serdesstrobe),
    .reset          (reset),
    .gclk           (sample_clk),
    .bitslip        (bitslip),
    // .data_out       ({frame_out, data_out_b, data_out_a}),
    .data_out       (data_out),
    .debug_in       (),
    .debug          (),
    .delayVals      ({del_fr, del_b, del_a})
);

always @(posedge sample_clk) begin
    bitslip <= 0;
    // if ((cc % 20) == 0) bitslip <= 1;
    if (cc == 100) bitslip <= 1;
end

endmodule
