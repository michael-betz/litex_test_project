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

// Request shall not change while valid is high
assign f_request = {
	source_first,
	source_last,
	source_payload_data,
	source_payload_last_be,
	source_payload_error
};
always @(posedge sys_clk)
	if (f_past_valid && $past(source_valid) && !$past(source_ready))
		assert(f_request == $past(f_request));

`endif
