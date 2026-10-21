# Direct native initialization: no ORFS util/load hooks or hidden REPORTS_DIR.
set out /work/sta
file mkdir $out
set platform /frozen/flow/platforms/nangate45
foreach cmd {read_liberty read_db read_sdc define_process_corner set_extraction_rules_file extract_parasitics write_spef read_spef report_checks report_wns report_tns report_units check_setup ord::get_db_block} {
  if {[llength [info commands $cmd]] == 0} {error "HOLD missing STA command $cmd"}
  help $cmd
}
read_liberty $platform/lib/NangateOpenCellLibrary_typical.lib
read_db /inputs/6_final.odb
# Master-terminal directions come from the same native database, not Yosys.
set pins [open $out/pin-directions.tsv w]
foreach inst [[ord::get_db_block] getInsts] {
  set master [$inst getMaster]
  foreach term [$master getMTerms] {
    puts $pins "[$master getName]\t[$term getName]\t[$term getIoType]"
  }
}
close $pins
read_sdc /inputs/6_final.sdc
source $platform/setRC.tcl
# Exactly the extraction sequence used by frozen final_outputs.tcl.
define_process_corner -ext_model_index 0 X
set_extraction_rules_file $platform/rcx_patterns.rules
extract_parasitics
write_spef $out/reconstructed.spef
read_spef $out/reconstructed.spef
# Capture via process stdout; this command has no portable > argument.
puts "VERIEDA_REPORT_BEGIN units"
flush stdout
report_units
flush stdout
puts "VERIEDA_REPORT_END units"
flush stdout
# Capture via process stdout; this command has no portable > argument.
puts "VERIEDA_REPORT_BEGIN wns"
flush stdout
report_wns -max -digits 9
flush stdout
puts "VERIEDA_REPORT_END wns"
flush stdout
# Capture via process stdout; this command has no portable > argument.
puts "VERIEDA_REPORT_BEGIN tns"
flush stdout
report_tns -max -digits 9
flush stdout
puts "VERIEDA_REPORT_END tns"
flush stdout
report_checks -path_delay max -group_path_count 10000 -endpoint_path_count 1 \
  -slack_max 0 -sort_by_slack -no_line_splits -format full_clock_expanded \
  -fields {fanout capacitance slew input_pin net} -digits 9 > $out/all_setup.rpt
report_checks -path_delay max -group_path_count 20 -endpoint_path_count 1 \
  -sort_by_slack -no_line_splits -format full_clock_expanded \
  -fields {fanout capacitance slew input_pin net} -digits 9 > $out/top_setup.rpt
check_setup -verbose > $out/coverage.rpt
