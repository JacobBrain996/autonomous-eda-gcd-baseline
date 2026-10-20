# Fresh native context for each role; no shell/Tcl evaluation by Python.
if {![info exists ::env(VERIEDA_SNAPSHOT_ROLE)]} {error "HOLD missing snapshot role"}
set role $::env(VERIEDA_SNAPSHOT_ROLE)
if {$role ni {reference candidate}} {error "HOLD invalid snapshot role"}
set out /work/constraints/$role
file mkdir $out
set platform /frozen/flow/platforms/nangate45
foreach cmd {read_liberty read_db read_sdc write_sdc report_units check_setup ord::get_db_block} {
  if {[llength [info commands $cmd]] == 0} {error "HOLD missing snapshot command $cmd"}
}
read_liberty $platform/lib/NangateOpenCellLibrary_typical.lib
read_db /inputs/6_final.odb
if {$role eq "reference"} {
  read_sdc /frozen/flow/designs/nangate45/gcd/constraint.sdc
} else {
  read_sdc /inputs/6_final.sdc
}
write_sdc -no_timestamp $out/evaluated.sdc
report_units > $out/units.rpt
check_setup -verbose > $out/coverage.rpt
set f [open $out/ports.tsv w]
foreach term [[ord::get_db_block] getBTerms] {
  puts $f "[$term getName]\t[$term getIoType]"
}
close $f
