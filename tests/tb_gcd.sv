// Candidate testbench. NOT COMPILED/RUN in this Windows audit.
// Deterministic directed cases + explicit LCG seed; independent modulo oracle.
`timescale 1ns/1ps
module tb_gcd;
  reg clk = 0;
  always #5 clk = ~clk;
  reg reset = 1;
  reg [31:0] req_msg = 0;
  reg req_val = 0;
  wire req_rdy;
  wire [15:0] resp_msg;
  reg resp_rdy = 0;
  wire resp_val;
  integer cases = 0;
  integer i;
  reg [31:0] rng = 32'h5eda0001;
  reg [15:0] a, b;
  gcd dut(.clk(clk), .reset(reset), .req_msg(req_msg), .req_val(req_val),
          .req_rdy(req_rdy), .resp_msg(resp_msg), .resp_val(resp_val), .resp_rdy(resp_rdy));

  function automatic [15:0] reference_gcd(input [15:0] x, input [15:0] y);
    reg [15:0] u, v, t;
    begin
      u=x; v=y;
      while (v != 0) begin t=u%v; u=v; v=t; end
      reference_gcd=u;
    end
  endfunction

  task automatic check_case(input [15:0] x, input [15:0] y);
    integer cycles, hold_cycle;
    reg [15:0] expected;
    begin
      expected=reference_gcd(x,y);
      @(negedge clk);
      req_msg={x,y}; req_val=1; resp_rdy=0;
      cycles=0;
      while (req_rdy !== 1'b1) begin
        @(negedge clk);
        cycles=cycles+1;
        if (cycles>200000) $fatal(1,"request timeout a=%0d b=%0d",x,y);
      end
      @(posedge clk); // request handshakes here
      @(negedge clk); req_val=0;
      cycles=0;
      while (resp_val !== 1'b1) begin
        @(negedge clk);
        cycles=cycles+1;
        if (cycles>200000) $fatal(1,"response timeout a=%0d b=%0d",x,y);
      end
      if (resp_msg !== expected)
        $fatal(1,"mismatch a=%0d b=%0d expected=%0d actual=%0d",x,y,expected,resp_msg);
      // Backpressure must retain both valid and data across clock edges.
      for (hold_cycle=0; hold_cycle<3; hold_cycle=hold_cycle+1) begin
        @(negedge clk);
        if (resp_val !== 1'b1 || resp_msg !== expected)
          $fatal(1,"response not stable under backpressure");
      end
      resp_rdy=1;
      @(posedge clk);
      @(negedge clk); resp_rdy=0;
      cases=cases+1;
    end
  endtask

  initial begin
    repeat (4) @(negedge clk);
    reset=0;
    check_case(0,0);
    check_case(0,65535);
    check_case(65535,0);
    check_case(1,1);
    check_case(65535,65535);
    check_case(65535,1);
    check_case(1,65535);
    check_case(48,18);
    check_case(18,48);
    check_case(37,23);
    check_case(32768,256);
    check_case(65535,65534);
    for(i=0;i<64;i=i+1) begin
      rng=32'd1664525*rng+32'd1013904223; a={8'd0,rng[15:8]};
      rng=32'd1664525*rng+32'd1013904223; b={8'd0,rng[15:8]};
      check_case(a,b);
    end
    if (cases != 76) $fatal(1,"unexpected case count");
    $display("TESTED_PASS cases=%0d seed=5eda0001 (simulation only, not formal proof)", cases);
    $finish;
  end
  initial begin
    #100000000;
    $fatal(1,"global watchdog timeout");
  end
endmodule
