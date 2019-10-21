

`timescale 1 ns / 1 ns

module dsp #(
    parameter LO_FTW=1
) (
    input               clk,
    input               reset,
    input signed [13:0] adc_ref,
    input signed [13:0] adc_a,
    input signed [13:0] adc_b,
    input signed [13:0] adc_c
);
    wire [31:0] dds_ftw = LO_FTW;
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

    wire signed [19:0] result_i;
    wire signed [19:0] result_q;
    wire strobe_cc;

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
    iq_trace #(
        .dw        (14),
        .oscw      (18),
        .davr      (3),
        .ow        (28),
        .rw        (20),
        .pcw       (13),
        .shift_base(7),
        .nadc      (4),
        .aw        (8)
    ) iq_trace_inst (
        .clk       (clk),
        .reset     (reset),
        .trig      (1'b1),
        .trig_mode (2'd0),
        .adcs      ({adc_c, adc_b, adc_a, adc_ref}),
        .cosa      (lo_cos),
        .sina      (lo_sin),

        .cic_period(13'd48),
        .cic_shift (4'd0),

        .result_i  (result_i),
        .result_q  (result_q),
        .strobe_cc (strobe_cc)
        // .keep      (keep)

    );


    // ---------------------------------
    //  arctan2(I, Q) (cordic)
    // ---------------------------------
    // convert IQ to polar coordinates to get
    // magnitude / angle
    // pipelined for `nadc` channels
    wire signed [19:0] mag_out;
    wire signed [20:0] phase_out;
    cordicg_b22 #(
        .nstg       (20),   // latency - 1
        .width      (20),
        .def_op     (2'd1)  // rect to polar, yout = 0
    ) cordic_r2p (
        .clk        (clk),
        .opin       (2'd1),
        .xin        (result_i),
        .yin        (result_q),
        .phasein    (21'h0),
        .yout       (),
        .xout       (mag_out),
        .phaseout   (phase_out)
    );

    wire strobe_r2p;
    reg_delay #(
        .dw (1),
        .len(21)
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
    reg [19:0] mag_ref = 20'h0;
    reg [19:0] mag_a = 20'h0;
    reg [19:0] mag_b = 20'h0;
    reg [19:0] mag_c = 20'h0;
    reg signed [20:0] phase_ref = 21'h0;
    reg signed [20:0] phase_a = 21'h0;
    reg signed [20:0] phase_b = 21'h0;
    reg signed [20:0] phase_c = 21'h0;

    reg [ 3:0] sig_cnt = 4'h0;
    always @(posedge clk) begin
        sig_cnt <= 2'h0;
        if (strobe_r2p) begin
            sig_cnt <= sig_cnt + 1;
            case (sig_cnt)
                2'h0: begin
                    mag_ref <= mag_out;
                    phase_ref <= phase_out;
                end
                2'h1: begin
                    mag_a <= mag_out;
                    phase_a <= phase_out - phase_ref;
                end
                2'h2: begin
                    mag_b <= mag_out;
                    phase_b <= phase_out - phase_ref;
                end
                2'h3: begin
                    mag_c <= mag_out;
                    phase_c <= phase_out - phase_ref;
                end
            endcase // sig_cnt
        end
    end
endmodule
