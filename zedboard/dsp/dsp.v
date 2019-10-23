

`timescale 1 ns / 1 ns

module dsp #(
    parameter W_CORDIC = 31
) (
    input               clk,
    input               reset,

    input signed [13:0] adc_ref,
    input signed [13:0] adc_a,
    input signed [13:0] adc_b,
    input signed [13:0] adc_c,

    input        [31:0] dds_ftw,
    input        [12:0] decimation,

    output reg   [W_CORDIC - 1:0] mag_ref,
    output reg   [W_CORDIC - 1:0] mag_a,
    output reg   [W_CORDIC - 1:0] mag_b,
    output reg   [W_CORDIC - 1:0] mag_c,

    output reg signed [W_CORDIC:0] phase_ref,
    output reg signed [W_CORDIC:0] phase_a,
    output reg signed [W_CORDIC:0] phase_b,
    output reg signed [W_CORDIC:0] phase_c,

    output reg out_strobe
);
    wire signed [17:0] lo_sin;
    wire signed [17:0] lo_cos;

    // ---------------------------------
    //  Generate local oscillator (LO)
    // ---------------------------------
    // shared for all channels
    rot_dds #(
        .lo_amp         (18'd79590)
    ) dds_inst (
        .clk            (clk),
        .reset          (reset),
        .phase_step_h   (dds_ftw[31:12]),
        .phase_step_l   (dds_ftw[11:0]),
        .modulo         (12'h0),
        .cosa           (lo_cos),
        .sina           (lo_sin)
    );

    wire signed [W_CORDIC - 1:0] result_iq;
    reg signed [W_CORDIC - 1:0] result_iq_d;
    wire strobe_cc;
    always @(posedge clk) result_iq_d <= result_iq;

    // ---------------------------------
    //  Digital down-converter
    // ---------------------------------
    //  * complex multiplication with complex LO to
    //    move signal of interest close to 0 Hz
    //  * Lowpass + decimation by factor of `cic_period`
    //  * Implemented as polyphase CIC filter,
    //    pipelined for `nadc` channels
    //  * outputs IQ of first channel on `strobe_cc` rising edge
    //  * `strobe_cc` falling edge after outputting last channel
    //  * contains circular waveform buffer functionality
    //    (not used yet)
    ddc #(
        .dw        (14),
        .oscw      (18),
        .davr      (3),
        .ow        (W_CORDIC),
        .rw        (W_CORDIC),
        .pcw       (13),
        .shift_base(7),
        .nadc      (4)
    ) ddc_inst (
        .clk       (clk),
        .reset     (reset),
        .adcs      ({adc_c, adc_b, adc_a, adc_ref}),
        .cosa      (lo_cos),
        .sina      (lo_sin),

        .cic_period(decimation),
        .cic_shift (4'd0),

        .result_iq (result_iq),
        .strobe_cc (strobe_cc)
    );

    // ---------------------------------
    //  arctan2(I, Q) (cordic)
    // ---------------------------------
    // convert IQ to polar coordinates to get
    // magnitude / angle
    // pipelined for `nadc` I,Q channels
    // every second clock cycle is a valid result
    // ... only after 21 cycle after strobe_cc
    // ... only for 4 channels
    wire signed [W_CORDIC - 1: 0] mag_out;
    wire signed [W_CORDIC: 0] phase_out;

    cordicg_b32 #(
        .nstg       (W_CORDIC), // latency - 1
        .width      (W_CORDIC),
        .def_op     (2'd1)  // rect to polar, yout = 0
    ) cordic_r2p (
        .clk        (clk),
        .opin       (2'd1),
        .xin        (result_iq_d), // I
        .yin        (result_iq),   // Q
        .phasein    (32'h0),
        .yout       (),
        .xout       (mag_out),
        .phaseout   (phase_out)
    );

    wire strobe_r2p;
    reg_delay #(
        .dw (1),
        .len(W_CORDIC + 2)
    ) strobe_delay (
        .clk  (clk),
        .reset(1'b0),
        .gate (1'b1),
        .din  (strobe_cc),
        .dout (strobe_r2p)
    );

    // ---------------------------------
    //  de-serialize (latch) the stream
    // ---------------------------------
    // also calculate phase difference to reference channel
    reg [ 4:0] sig_cnt = 5'h0;
    always @(posedge clk) begin
        sig_cnt <= 5'h0;
        out_strobe <= 0;
        if (strobe_r2p) begin
            sig_cnt <= sig_cnt + 1;
            case (sig_cnt)
                5'h0: begin
                    mag_ref <= mag_out;
                    phase_ref <= phase_out;
                end
                5'h2: begin
                    mag_a <= mag_out;
                    phase_a <= phase_out - phase_ref;
                end
                5'h4: begin
                    mag_b <= mag_out;
                    phase_b <= phase_out - phase_ref;
                end
                5'h6: begin
                    mag_c <= mag_out;
                    phase_c <= phase_out - phase_ref;
                    out_strobe <= 1;
                end
            endcase // sig_cnt
        end
    end
endmodule
