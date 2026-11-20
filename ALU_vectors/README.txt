EE 477L final project: test vectors for the 8-bit ALU with FSM controller
=========================================================================
One folder per test (see Section 10 of the Phase 1 document):
  t1_rca8  t2_logic8  t3_shift8  t4_result_stage  t5_fsm_dec  t6_fsm_next  t7_fsm_out
  t8_fsm_ctrl  t9_alu8  t10_dff_r

Each folder contains
  <test>.vec    ONE Cadence digital vector file with all inputs of the test
                (header: radix / io / vname; timing: tunit 1ns, trise, tfall, vih = VDD, vil = 0;
                 then one row per time: time followed by one 0/1 per column).
                The column names (vname) are the net names to use in the test bench.
  expected.csv  strobe times (ns) and the expected output values

Logic 1 = vih = 1.0 V (VDD = 1.0 V).  To use another supply:   python3 make_vectors.py <VDD>
Clocked tests (t4, t8, t9, t10) have clk and rst as columns: clock rising edges at 5, 15, 25 ... ns.
Only inputs are in the .vec files; compare the outputs with expected.csv at the strobe times.
