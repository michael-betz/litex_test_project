`timescale 1 ns / 1 ps

module hello_LTC_tb;
    localparam real XTAL_PERIOD = 1e9 / 200e6;    // Simulated clock period in [ns]
    localparam real FR_CLK_PERIOD = 1e9 / 125e6;  // SDR
    localparam real DCO_CLK_PERIOD = FR_CLK_PERIOD / 4.0; // DDR
    // Testpattern! LSB ends up on on LVDS lane B!
    localparam [15:0] TP = 16'b0011110111011010;

    //------------------------------------------------------------------------
    // Clock and fake LVDS lanes generation
    //------------------------------------------------------------------------
    reg xtal_clk = 1;
    reg fr_clk = 1;
    reg dco_clk_p = 0;
    reg out_a_p = 0;
    reg out_b_p = 0;
    always #(XTAL_PERIOD / 2) xtal_clk = ~xtal_clk;
    always #(FR_CLK_PERIOD / 2) fr_clk = ~fr_clk;
    initial begin
        #(DCO_CLK_PERIOD / 4);
        forever #(DCO_CLK_PERIOD / 2) dco_clk_p = ~dco_clk_p;
    end

    reg [15:0] temp = 0;
    always begin
        // Craft 2 x 8 bit DDR signals according to timing diagram in LTC datasheet
        temp = TP;
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
            $dumpfile("hello_LTC.vcd");
            $dumpvars(5, hello_LTC_tb);
        end
        repeat (3) @(posedge xtal_clk);
        reset <= 0;
        #5000
        $finish();
    end


    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    top dut (
        .serial_cts     (1'b0),
        .serial_rts     (1'b0),
        .serial_rx      (1'b0),
        .clk200_p       (xtal_clk),
        .clk200_n       (~xtal_clk),
        .cpu_reset      (reset),
        .LTC_SPI_miso   (1'b0),
        .LTC_FR_p       (fr_clk),
        .LTC_FR_n       (~fr_clk),
        // .LTC_DCO_p      (dco_clk_p),
        // .LTC_DCO_n      (~dco_clk_p),
        .LTC_OUT2_a_p   (out_a_p),
        .LTC_OUT2_a_n   (~out_a_p),
        .LTC_OUT2_b_p   (1'b0),
        .LTC_OUT2_b_n   (1'b1)
    );
endmodule
