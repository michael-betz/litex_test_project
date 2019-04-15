`timescale 1 ns / 1 ps

module hello_ETH_tb;
    //------------------------------------------------------------------------
    // Clock and fake LVDS lanes generation
    //------------------------------------------------------------------------
    reg clk125=1, clksys=1, clkxtal=1;
    always #(1e9 / 125e6 / 2) clk125 = ~clk125;
    // Reducing clksys <= 110 MHz causes glitches on eth_tx_en !!!
    // always #(1e9 / 125e6 / 2) clksys = ~clksys;
    always #(1e9 / 200e6 / 2) clkxtal = ~clkxtal;

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("hello_ETH.vcd");
            $dumpvars(5, hello_ETH_tb);
        end
        repeat (3) @(posedge clkxtal);
        reset <= 0;
        #5000
        $finish();
    end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    integer cc = 0;
    integer i = 0;
    wire eth_clocks_gtx, eth_tx_en, eth_rst_n;
    wire [7:0] eth_tx_data;
    reg [7:0] eth_rx_data = 0;
    reg eth_rx_dv = 0;
    reg [7:0] ethData [69:0];
    initial $readmemh("test/arp_req.hex", ethData);
    always @(posedge eth_clocks_gtx) begin
        if (eth_rst_n == 0) begin
            cc <= 0;
            i <= 0;
            eth_rx_dv <= 0;
            eth_rx_data <= 0;
        end else begin
            cc <= cc + 1;
            eth_rx_dv <= 1'b0;
            if (cc == 10 || cc == 220 || cc == 420 || eth_rx_dv) begin
                if (i < 70) begin
                    i <= i + 1;
                    eth_rx_dv <= 1'b1;
                    eth_rx_data <= ethData[i];
                end else
                    i <= 0;
            end
        end
    end

    hello_ETH dut (
        .serial_cts     (1'b0),
        .serial_rts     (1'b0),
        .serial_rx      (1'b0),
        .clk200_p       (clkxtal),
        .clk200_n       (~clkxtal),
        // .clk156_p       (clksys),
        // .clk156_n       (~clksys),
        .cpu_reset      (reset),
        .eth_int_n      (1'b0),            // Not used
        .eth_rx_er      (1'b0),            // not used
        .eth_col        (1'b0),            // Collision (not used)
        .eth_crs        (1'b0),            // Carrier sense (not used)
        .eth_rx_dv      (eth_rx_dv),
        .eth_rx_data    (eth_rx_data),     // from phy to fpga
        .eth_clocks_rx  (clk125),          // from phy (cable) to FPGA
        .eth_clocks_gtx (eth_clocks_gtx),  // from FPGA to PHY
        .eth_tx_data    (eth_tx_data),
        .eth_tx_en      (eth_tx_en),
        .eth_rst_n      (eth_rst_n)        // Reset phy
    );

endmodule

