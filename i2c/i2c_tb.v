`timescale 1 ns / 1 ns

module i2c_tb;
    localparam real XTAL_PERIOD = 1e9 / 156e6;    // System clock period in [ns]

    reg xtal_clk = 1;
    always #(XTAL_PERIOD / 2) xtal_clk = ~xtal_clk;

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("i2c.vcd");
            $dumpvars(5, i2c_tb);
        end
        repeat (3) @(posedge xtal_clk);
        reset <= 0;
        #5000
        $finish();
    end

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    integer cc = 0;
    integer i = 0;
    
    i2c dut (
        .start(1'b1),
        .done(),
        .mode(2'd1),
        .sys_clk(xtal_clk),
        .sys_rst(reset)
	
    );

endmodule

