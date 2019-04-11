`timescale 1 ns / 1 ns

module hello_ETH_tb;
    localparam real XTAL_PERIOD = 1e9 / 200e6;    // System clock period in [ns]
    localparam real RX_CLK_PERIOD = 1e9 / 125e6;  // PHY RX clock

    //------------------------------------------------------------------------
    // Clock and fake LVDS lanes generation
    //------------------------------------------------------------------------
    reg xtal_clk = 1;
    reg eth_clocks_rx = 1;
    always #(XTAL_PERIOD / 2) xtal_clk = ~xtal_clk;
    always #(RX_CLK_PERIOD / 2) eth_clocks_rx = ~eth_clocks_rx;

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("hello_ETH.vcd");
            $dumpvars(5, hello_ETH_tb);
        end
        repeat (3) @(posedge xtal_clk);
        reset <= 0;
        #2000  // Why does vvp hang ???
        $finish();
    end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    integer cc = 0;
    wire [7:0] eth_rx_data;
    wire [7:0] eth_tx_data;
    wire eth_rx_dv, eth_clocks_gtx;
    always @(posedge eth_clocks_gtx) begin
        cc <= cc + 1;
    end
    hello_ETH dut (
        .serial_cts     (1'b0),
        .serial_rts     (1'b0),
        .serial_rx      (1'b0),
        .clk200_p       (xtal_clk),
        .clk200_n       (~xtal_clk),
        .cpu_reset      (reset)
        // .eth_int_n      (1'b0),            // Not used
        // .eth_rx_er      (1'b0),            // not used
        // .eth_col        (1'b0),            // Collision (not used)
        // .eth_crs        (1'b0),            // Carrier sense (not used)
        // .eth_rx_dv      (eth_rx_dv),
        // .eth_rx_data    (eth_rx_data),     // from phy to fpga
        // .eth_clocks_rx  (eth_clocks_rx),   // from phy (cable) to FPGA
        // .eth_clocks_gtx (eth_clocks_gtx),  // from FPGA to PHY
        // .eth_tx_data    (eth_tx_data),
        // .eth_rst_n      (),                // Reset phy
        // .eth_tx_en      ()
    );

endmodule

