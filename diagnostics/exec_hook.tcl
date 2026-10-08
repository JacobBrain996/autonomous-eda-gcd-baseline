# External instrumentation only. Frozen ORFS files are not edited.
namespace eval ::lecdiag {}
proc ::lecdiag::append_record {name value} {
  if {![info exists ::env(DIAG_DIR)]} {return}
  set path [file join $::env(DIAG_DIR) $name]
  if {[file exists $path] && [file size $path] >= 8388608} {return}
  set f [open $path a]
  puts $f [string range $value 0 65535]
  if {[string length $value] > 65536} {puts $f "DIAGNOSTIC_RECORD_TRUNCATED=TRUE"}
  close $f
}
rename ::exec ::lecdiag::original_exec
proc ::exec {args} {
  set is_kepler [expr {[info exists ::env(KEPLER_FORMAL_EXE)] &&
    [lindex $args 0] eq $::env(KEPLER_FORMAL_EXE)}]
  set is_lec_grep [expr {[lindex $args 0] eq "grep" &&
    [string match */4_rsz_lec_check.log [lindex $args end]]}]
  set tracked [expr {$is_kepler || $is_lec_grep}]
  set call $args
  if {$tracked} {
    catch {::lecdiag::append_record effective-command.txt [list original_argv $args]}
    if {$is_kepler && ![info exists ::env(DIAG_TEST_NO_LAUNCHER)]} {
      set call [list python3 /diagnostic/observe.py --output $::env(DIAG_DIR) -- {*}$args]
    }
  }
  set code [catch {uplevel 1 [list ::lecdiag::original_exec {*}$call]} result options]
  if {$tracked && $code != 0} {
    # Logging must never replace or swallow the underlying failure.
    catch {
      ::lecdiag::append_record tcl-exec-error.txt [list original_argv $args result $result options $options]
    }
  }
  return -options $options $result
}
