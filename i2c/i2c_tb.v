`timescale 1 ns / 1 ns

module i2c_tb;
    localparam real SYS_PERIOD = 1e9 / 51.2e6;    // System clock period in [ns]

    reg sys_clk = 1;
    always #(SYS_PERIOD / 2) sys_clk = ~sys_clk;

    //------------------------------------------------------------------------
    //  Handle the power on Reset
    //------------------------------------------------------------------------
    reg reset = 1;
    reg start = 0;
    wire done;
    reg [1:0] mode = 2'd0;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("i2c.vcd");
            $dumpvars(5, i2c_tb);
        end
        repeat (3) @(posedge sys_clk);
        reset <= 0;
        repeat (25) @(posedge sys_clk);

        i2c_action(2'd2);
        i2c_action(2'd1);
        i2c_action(2'd3);

        repeat (25) @(posedge sys_clk);
        $finish();
    end

    task i2c_action;
        input [1:0] i_mode;
        begin
            @ (posedge sys_clk);
            mode <= i_mode;
            start <= 1;
            @(posedge sys_clk);
            start <= 0;
            @(posedge sys_clk);
            wait (done);
        end
    endtask

    //------------------------------------------------------------------------
    //  DUT
    //------------------------------------------------------------------------
    i2c dut (
        .start(start),
        .mode(mode),
        .done(done),
        .sys_clk(sys_clk),
        .sys_rst(reset)
    );

endmodule

