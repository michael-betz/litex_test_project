`timescale 1 ns / 1 ns

module dsp_tb;
    localparam pi = 3.141592653589793;
    // ADC sampling clock f_s [Hz]
    // chosen for f_RF / f_ADC = 4.25
    localparam F_ADC = 117552941;
    // localparam F_ADC = 124000000;
    // Simulated clock period in [ns]
    localparam T_ADC = 1000000000 / F_ADC;
    reg clk_adc = 1;
    integer f;
    always #(T_ADC / 2) begin
        clk_adc = ~clk_adc;
    end

    // ------------------------------------------------------------------------
    //  Simulate ADC signals
    // ------------------------------------------------------------------------
    // ALS MO reference and phase shifted signal under test
    localparam F_REF = 499600000;  // [Hz]
    localparam OMEGA_REF = (1.0 / F_ADC * 2.0 * pi * F_REF);
    // Phase shift between adc_ref and adc_a
    localparam THETA_A = 0;
    localparam THETA_B = 2.0 / 3 * pi;
    localparam THETA_C = 4.0 / 3 * pi;

    // As we undersample and operate on a non-inverted nyquist band,
    // signal will appear at:
    localparam F_REF_US = ((1.0 * F_REF / F_ADC) % 1) * F_ADC;

    reg signed [13:0] adc_ref = 14'h0;
    reg signed [13:0] adc_a = 14'h0;
    reg signed [13:0] adc_b = 14'h0;
    reg signed [13:0] adc_c = 14'h0;

    reg strobe_cc_d = 0;
    reg signed [19:0] adc_ref_dc_i = 20'h0;
    reg signed [19:0] adc_ref_dc_q = 20'h0;


    integer sample_cnt = 0;
    always @(posedge clk_adc) begin
        sample_cnt <= sample_cnt + 1;
        adc_ref <= ((1 << 12) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF);
        adc_a <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_A);
        adc_b <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_B);
        adc_c <= ((1 << 13) - 1) * $sin(1.0 * sample_cnt * OMEGA_REF + THETA_C);
        if (!reset) begin
            strobe_cc_d <= dsp_inst.strobe_cc;
            adc_ref_dc_i <= 20'h0;
            adc_ref_dc_q <= 20'h0;
            if (dsp_inst.strobe_cc && !strobe_cc_d) begin
                adc_ref_dc_i <= dsp_inst.result_i;
                adc_ref_dc_q <= dsp_inst.result_q;
            end
            $fwrite(
                f,
                "%d, %d, %d, %d, %d, %d\n",
                adc_ref, 0,
                dsp_inst.lo_cos, dsp_inst.lo_sin,
                adc_ref_dc_i, adc_ref_dc_q
            );
        end
    end

    // ------------------------------------------------------------------------
    //  Handle the power on Reset
    // ------------------------------------------------------------------------
    reg reset = 1;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("dsp.vcd");
            $dumpvars(5,dsp_tb);
        end
        f = $fopen("output.txt","w");
        $fwrite(f, "adc_ref, lo, adc_ref_dc\n");
        repeat (100) @(posedge clk_adc);
        reset <= 0;
        repeat (16000) @(posedge clk_adc);
        $fclose(f);
        $finish;
    end

    // ------------------------------------------------------------------------
    //  Instantiate the unit under test
    // ------------------------------------------------------------------------
    // IF at 10 kHz offset (rate at which phase_ref rolls over)
    localparam LO_FTW = 1.0 * (F_REF_US + 10000) / F_ADC * 2**32;
    wire [31:0] dds_ftw = LO_FTW;
    dsp #(
        .LO_FTW         (LO_FTW)
    ) dsp_inst (
        .clk            (clk_adc),
        .reset          (reset),
        .adc_ref        (adc_ref),
        .adc_a          (adc_a),
        .adc_b          (adc_b),
        .adc_c          (adc_c)
    );

endmodule
