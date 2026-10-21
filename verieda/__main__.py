import argparse,hashlib,json
from pathlib import Path
from .evidence import inspect
from .constraints import compare_sdc
from .formal import observe_yosys
from .native import inspect_acceptance
from .case import load_case,read_json
from .policy import propose
from .adoption import evaluate

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
    p=sub.add_parser('plan',help='load pinned evidence and propose legal bounded actions; no execution')
    p.add_argument('--profile',required=True);p.add_argument('--smoke',required=True);p.add_argument('--acceptance',required=True)
    p.add_argument('--budget-seconds',type=int,default=0);p.add_argument('--history')
    p=sub.add_parser('evaluate',help='independently compare before/after evidence; never trusts policy success')
    for side in ('before','after'):
        for part in ('profile','smoke','acceptance'):p.add_argument('--'+side+'-'+part,required=True)
    p.add_argument('--candidate',required=True)
    args=parser.parse_args()
    try:
        if args.command=='plan':
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            state={'state':case,'decision':propose(case,args.budget_seconds,read_json(args.history) if args.history else [])};rc=0
        elif args.command=='evaluate':
            before=load_case(read_json(args.before_profile),args.before_smoke,args.before_acceptance)
            after=load_case(read_json(args.after_profile),args.after_smoke,args.after_acceptance)
            state=evaluate(before,after,read_json(args.candidate));rc=0
        elif args.command=='inspect':
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
