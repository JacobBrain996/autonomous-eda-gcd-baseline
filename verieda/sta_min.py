"""Offline hold recipe and bounded observations, never a final Timing certificate."""
import hashlib,math,re
from pathlib import Path

STA_PREFIX_SHA256='a9c229f68be41f53193a89a3c1e61b27ce83e5d1c2ca4f749a4cba5ac255133d'
HOLD_SUFFIX=b"""
# VeriEDA independent min-delay observations; initialization above is unchanged.
puts "VERIEDA_REPORT_BEGIN hold_wns"
flush stdout
report_wns -min -digits 9
flush stdout
puts "VERIEDA_REPORT_END hold_wns"
puts "VERIEDA_REPORT_BEGIN hold_tns"
flush stdout
report_tns -min -digits 9
flush stdout
puts "VERIEDA_REPORT_END hold_tns"
flush stdout
report_checks -path_delay min -group_path_count 10000 -endpoint_path_count 1 \
  -slack_max 0 -sort_by_slack -no_line_splits -format full_clock_expanded \
  -fields {fanout capacitance slew input_pin net} -digits 9 > $out/all_hold.rpt
report_checks -path_delay min -group_path_count 20 -endpoint_path_count 1 \
  -sort_by_slack -no_line_splits -format full_clock_expanded \
  -fields {fanout capacitance slew input_pin net} -digits 9 > $out/top_hold.rpt
"""

def build_hold_script():
    """Keep the actually executed initializer, not a guessed native setup.

    GCD/Nangate45 fixed mount convention; runtime input/binary/OCI admission,
    process limits, return status, archive binding and cloud permission remain
    the caller's responsibility. This function only returns bytes.
    """
    p=Path(__file__).resolve().parents[1]/'acceptance/sta.tcl'
    prefix=p.read_bytes()
    if hashlib.sha256(prefix).hexdigest()!=STA_PREFIX_SHA256:raise ValueError('reviewed native STA initialization changed')
    return prefix+HOLD_SUFFIX


def observe_hold(return_code,text):
    result={'schema':'verieda.hold-observation.v1','observation':'HOLD_REPORT_FORMAT','hold_gate':'UNKNOWN',
            'metrics':None,'worst_hold_slack_ns':None,'issues':[],'certification':'NOT_CERTIFIED',
            'scope':'saved min WNS/TNS only; no object coverage, execution authentication or full Timing PASS'}
    try:
        if type(return_code) is not int:raise ValueError('integer native return code required')
        if not isinstance(text,str) or len(text)>16*1024*1024:raise ValueError('bounded text required')
        raw=text.encode()
        if len(raw)>16*1024*1024:raise ValueError('text byte budget exceeded')
        result.update(return_code=return_code,log_text_sha256=hashlib.sha256(raw).hexdigest())
        if return_code:
            result['observation']='TIMEOUT' if return_code==124 else 'TOOL_ERROR'
            return result
        def section(label):
            begin='VERIEDA_REPORT_BEGIN '+label;end='VERIEDA_REPORT_END '+label
            lines=text.splitlines()
            b=[i for i,s in enumerate(lines) if s==begin];e=[i for i,s in enumerate(lines) if s==end]
            if len(b)!=1 or len(e)!=1 or e[0]<=b[0]:raise ValueError('missing/ambiguous report section '+label)
            body='\n'.join(lines[b[0]+1:e[0]])
            if 'VERIEDA_REPORT_BEGIN ' in body or 'VERIEDA_REPORT_END ' in body:raise ValueError('nested report markers')
            return body
        units=section('units')
        if re.findall(r'(?m)^\s*time\s+(\S+)\s*$',units)!=['1ns']:raise ValueError('one explicit time 1ns unit required')
        metrics={}
        for key,cmd in (('hold_wns','wns'),('hold_tns','tns')):
            rows=section(key).strip().splitlines()
            if len(rows)!=1:raise ValueError('ambiguous min metric '+key)
            m=re.fullmatch(r'\s*'+cmd+r'\s+min\s+(\S+)\s*',rows[0])
            if not m:raise ValueError('unsupported min metric format '+key)
            v=float(m[1])
            if not math.isfinite(v) or v>0:raise ValueError('min WNS/TNS must be finite and nonpositive')
            metrics[key]={'value':v,'unit':'ns'}
        w,t=(metrics[k]['value'] for k in ('hold_wns','hold_tns'))
        if (w<0)!=(t<0) or t>w:raise ValueError('inconsistent min WNS/TNS')
        result.update(metrics=metrics,observation='NEGATIVE_HOLD_REPORTED' if w<0 else 'NO_NEGATIVE_HOLD_REPORTED',
                      hold_gate='FAIL' if w<0 else 'UNKNOWN')
    except (ValueError,TypeError,UnicodeError) as ex:result['issues'].append(str(ex))
    return result
