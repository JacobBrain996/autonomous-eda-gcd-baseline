# Same OpenROAD and frozen formal implementation, new observational entry point.
source $::env(SCRIPTS_DIR)/util.tcl
source $::env(SCRIPTS_DIR)/formal_check.tcl
source /diagnostic/exec_hook.tcl
foreach name {LEC_CHECK SEC_CHECK KEPLER_FORMAL_EXE} {
  ::lecdiag::append_record effective-vars.txt [list $name $::env($name)]
}
if {![lec_check_enabled]} {error "HOLD: LEC is not enabled; diagnostic cannot silently bypass it"}
run_lec_test 4_rsz 4_before_rsz_lec.v 4_after_rsz_lec.v
