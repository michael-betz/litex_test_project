`timescale 1 ns / 1 ps

module IserdesSp6_tb;
    localparam real SYS_CLK_PERIOD = 1e9 / 100e6;    // Simulated clock period in [ns]
    localparam real FR_CLK_PERIOD = 1e9 / 125e6; // SDR
    localparam real DCO_CLK_PERIOD = FR_CLK_PERIOD / 4.0; // DDR
    // Testpattern! LSB ends up on on LVDS lane B!
    localparam [15:0] TP = 16'b0011110111011010;

    //------------------------------------------------------------------------
    // Clock and fake LVDS lanes generation
    //------------------------------------------------------------------------
    reg sys_clk = 1;
    reg fr_clk = 1;
    reg dco_clk_p = 0;
    reg out_a_p = 0;
    reg out_b_p = 0;
    always #(SYS_CLK_PERIOD / 2) sys_clk = ~sys_clk;
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
    integer pass=1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("IserdesSp6.vcd");
            $dumpvars(5, IserdesSp6_tb);
        end
        repeat (3) @(posedge sys_clk);
        reset <= 0;
        #4000
        if(pass)
            $display("PASS");
        else
            $display("FAIL");
        $finish();
    end


    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    reg bitslip = 0;
    wire sample_clk;
    wire [7:0] data_outs;
    wire [7:0] clk_data_out;
    top dut (
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
        .pll_reset      (reset),
        .pd_int_period  (32'd64),
        .id_auto_control(1'b1),
        .id_mux         (1'b0),
        .id_inc         (1'b0),
        .id_dec         (1'b0)
    );

    integer cc = 0;
    reg [7:0] tp_a = {TP[15], TP[13], TP[11], TP[9], TP[7], TP[5], TP[3], TP[1]};
    reg [7:0] tp_b = {TP[14], TP[12], TP[10], TP[8], TP[6], TP[4], TP[2], TP[0]};
    always @(posedge sample_clk) begin
        cc <= cc + 1;
        bitslip <= 0;
        if (cc == 100) bitslip <= 1;
        if (cc == 110) bitslip <= 1;
        if (cc == 120) bitslip <= 1;
        if (cc > 150) begin
            if ((data_outs != tp_a) || (clk_data_out != 8'h0F))
                pass = 0;
        end
    end
endmodule
