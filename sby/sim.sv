module sim ();
	wire sys_clk;
	wire sys_rst;

	reg sink_valid = 0;
	wire sink_ready;
	reg sink_first = 0;
	reg sink_last = 0;
	reg [31:0] sink_payload_data = 0;
	reg [3:0] sink_payload_last_be = 0;
	reg [3:0] sink_payload_error = 0;

	wire source_valid;
	reg source_ready = 0;
	wire source_first;
	wire source_last;
	wire [31:0] source_payload_data;
	wire [3:0] source_payload_last_be;
	wire [3:0] source_payload_error;

	anti_underflow au (
		.sink_valid            (                      ),
		.sink_ready            (sink_ready            ),
		.sink_first            (sink_first            ),
		.sink_last             (sink_last             ),
		.sink_payload_data     (sink_payload_data     ),
		.sink_payload_last_be  (sink_payload_last_be  ),
		.sink_payload_error    (sink_payload_error    ),
		.source_valid          (source_valid          ),
		.source_ready          (source_ready          ),
		.source_first          (source_first          ),
		.source_last           (source_last           ),
		.source_payload_data   (source_payload_data   ),
		.source_payload_last_be(source_payload_last_be),
		.source_payload_error  (source_payload_error  ),
		.sys_clk               (sys_clk               ),
		.sys_rst               (sys_rst               )
	);


endmodule
