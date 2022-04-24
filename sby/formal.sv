`ifdef FORMAL
reg f_past_valid = 0;

always @(posedge sys_clk) begin
	f_past_valid <= 1;

	// define / check RESET values
	if (!f_past_valid || $past(sys_rst)) begin
		assume(!sink_valid);
		assume(!source_ready);
		assert(sink_ready);
		assert(!source_valid);
	end

end

always @(*) begin
	assume(sys_rst == !f_past_valid);
	// cannot have ready without valid
	if (!source_valid)
		assume(!source_ready);
end

assign f_request_sink = {
	sink_valid,
	sink_first,
	sink_last,
	sink_payload_data,
	sink_payload_last_be,
	sink_payload_error
};
assign f_request_source = {
	source_valid,
	source_first,
	source_last,
	source_payload_data,
	source_payload_last_be,
	source_payload_error
};
always @(posedge sys_clk) begin
	// Request shall not change while valid is high
	if (f_past_valid && $past(sink_valid) && !$past(sink_ready))
		assume($stable(f_request_sink));
	if (f_past_valid && $past(source_valid) && !$past(source_ready))
		assert($stable(f_request_source));
	// Ready shall stay high if valid is low
	if (f_past_valid && $past(sink_ready) && $past(!sink_valid))
		assert(sink_ready);
	if (f_past_valid && $past(source_ready) && $past(!source_valid))
		assume(source_ready);
end

// 2 sequential input values shall be flowing out in the same order
(* anyconst *) wire [31:0] f_payload_a;
(* anyconst *) wire [31:0] f_payload_b;
reg f_sink_a = 0;
reg f_source_a = 0;
wire sink_strobe = sink_valid && sink_ready;
wire source_strobe = source_valid && source_ready;
always @(posedge sys_clk) begin
	if (!f_sink_a && sink_payload_data == f_payload_a && sink_strobe)
		f_sink_a <= 1;
	if (f_sink_a && sink_strobe) begin
		assume(sink_payload_data == f_payload_b);
		f_sink_a <= 0;
	end
	if (!f_source_a && source_payload_data == f_payload_a && source_strobe)
		f_source_a <= 1;
	if (f_source_a && source_strobe) begin
		assert(source_payload_data == f_payload_b);
		f_source_a <= 0;
	end
end


`endif
