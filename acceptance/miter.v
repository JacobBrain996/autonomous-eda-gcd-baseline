// Contract: two shared reset edges, then arbitrary defined inputs forever.
// Data registers are NOT initialized to zero; only this harness counter is.
module acceptance_miter(input clk, input reset, input req_val, input resp_rdy,
                        input [31:0] req_msg, output mismatch);
  reg [1:0] boot = 0;
  always @(posedge clk) if (boot < 2) boot <= boot + 1'b1;
  wire common_reset = boot < 2 ? 1'b1 : reset;
  wire gr, gv, tr, tv;
  wire [15:0] gm, tm;
  gold_core gold(.clk(clk), .reset(common_reset), .req_val(req_val),
                 .resp_rdy(resp_rdy), .req_msg(req_msg),
                 .req_rdy(gr), .resp_val(gv), .resp_msg(gm));
  gate_core gate(.clk(clk), .reset(common_reset), .req_val(req_val),
                 .resp_rdy(resp_rdy), .req_msg(req_msg),
                 .req_rdy(tr), .resp_val(tv), .resp_msg(tm));
  wire [17:0] gold_outputs = {gr, gv, gm};
  wire [17:0] gate_outputs = {tr, tv, tm};
  wire undefined_output = ((^gold_outputs) === 1'bx) || ((^gate_outputs) === 1'bx);
  assign mismatch = (boot == 2) && (undefined_output || (gold_outputs !== gate_outputs));
endmodule
