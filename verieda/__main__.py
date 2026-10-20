import argparse,hashlib,json
from pathlib import Path
from .evidence import inspect
from .constraints import compare_sdc
from .formal import observe_yosys
from .native import inspect_acceptance

def read(path,limit):
    p=Path(path)
    if p.stat().st_size>limit:raise ValueError('input size budget exceeded')
    raw=p.read_bytes()
    return raw,raw.decode('utf-8-sig')

def main():
    parser=argparse.ArgumentParser(prog='python -m verieda')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inspect',help='independently audit an ORFS artifact ZIP or directory')
    p.add_argument('artifact');p.add_argument('--expect',help='external experiment_identity.json')
    p.add_argument('--expected-sha256',help='trusted SHA256 of the original ZIP')
    p=sub.add_parser('inspect-acceptance',help='audit native acceptance bundle; no proof promotion')
    p.add_argument('artifact');p.add_argument('--expected-sha256')
    p=sub.add_parser('compare-constraints',help='strict exported-SDC literal profile; never executes Tcl')
    p.add_argument('reference');p.add_argument('candidate')
    p=sub.add_parser('observe-formal',help='classify a log; does not certify proof or witness')
    p.add_argument('log');p.add_argument('--return-code',required=True,type=int)
    args=parser.parse_args()
    try:
        if args.command=='inspect':
            state=inspect(args.artifact,args.expect,args.expected_sha256)
            rc=2 if state['gates']['evidence']=='FAIL' else 0
        elif args.command=='inspect-acceptance':
            state=inspect_acceptance(args.artifact,args.expected_sha256)
            rc=2 if state['gates']['evidence']=='FAIL' else 0
        elif args.command=='compare-constraints':
            a,at=read(args.reference,4*1024*1024);b,bt=read(args.candidate,4*1024*1024)
            state=compare_sdc(at,bt)
            state.update(reference_file_sha256=hashlib.sha256(a).hexdigest(),candidate_file_sha256=hashlib.sha256(b).hexdigest())
            rc={'EQUAL_WITHIN_PROFILE':0,'DIFFERENT':1,'UNKNOWN':2}[state['comparison']]
        else:
            raw,text=read(args.log,16*1024*1024);state=observe_yosys(args.return_code,text)
            state['raw_log_sha256']=hashlib.sha256(raw).hexdigest()
            rc=2 if state['formal_gate']=='ERROR' else 0
    except (OSError,ValueError,UnicodeError) as ex:
        state={'status':'UNKNOWN','error':str(ex),'command':args.command};rc=2
    print(json.dumps(state,indent=2,ensure_ascii=True,allow_nan=False))
    return rc

if __name__=='__main__':raise SystemExit(main())
