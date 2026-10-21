import argparse,hashlib,json
from pathlib import Path
from .evidence import inspect
from .constraints import compare_sdc,inspect_io_coverage
from .formal import observe_yosys
from .native import inspect_acceptance
from .case import load_case,read_json
from .policy import propose
from .adoption import evaluate
from .execution import prepare_action,execute_action
from .action_results import seal_action,inspect_action,advance_action
from .verification import load_subject,plan_verification,prepare_verification,verify_verification_package,review_candidate
from .formal_runtime import execute_formal
from .formal_review import inspect_formal
from .triage import diagnose
from .decision import decide
from .timing import explain_timing
from .sta_min import observe_hold,build_hold_script,STA_PREFIX_SHA256

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
    p=sub.add_parser('diagnose',help='bounded saved-log triage; no fault executable, ISA or design verdict')
    p.add_argument('artifact');p.add_argument('--expected-sha256',required=True)
    p=sub.add_parser('inspect-acceptance',help='audit native acceptance bundle; no proof promotion')
    p.add_argument('artifact');p.add_argument('--expected-sha256')
    p=sub.add_parser('inspect-io-coverage',help='check literal SDC I/O modes against native ports TSV; no full constraint PASS')
    p.add_argument('--sdc',required=True);p.add_argument('--ports',required=True)
    p=sub.add_parser('compare-constraints',help='strict exported-SDC literal profile; never executes Tcl')
    p.add_argument('reference');p.add_argument('candidate')
    p=sub.add_parser('observe-formal',help='classify a log; does not certify proof or witness')
    p.add_argument('log');p.add_argument('--return-code',required=True,type=int)
    p=sub.add_parser('prepare-hold-script',help='write exclusive native hold collector recipe; never executes')
    p.add_argument('--output',required=True)
    p=sub.add_parser('observe-hold',help='observe saved clipped min WNS/TNS; no final Timing PASS')
    p.add_argument('log');p.add_argument('--return-code',required=True,type=int)
    p=sub.add_parser('explain-timing',help='rank checked saved worst-path contributions; no EDA or causal claim')
    for part in ('profile','smoke','acceptance'):p.add_argument('--'+part,required=True)
    p=sub.add_parser('decide',help='join reference, candidate and verification evidence into one offline next action; never executes')
    for part in ('profile','smoke','acceptance'):p.add_argument('--'+part,required=True)
    p.add_argument('--budget-seconds',type=int,default=0,help='remaining native budget, excludes setup/billing')
    for part in ('result','expected-sha256','formal-result','formal-sha256','verification-package','formal-contract'):p.add_argument('--'+part)
    for part in ('profile','smoke','acceptance'):p.add_argument('--after-'+part)
    p.add_argument('--action-history',help='JSON list of pinned saved action archives; budget-seconds becomes total listed action plus future native budget')
    p=sub.add_parser('plan',help='load pinned evidence and propose legal bounded actions; no execution')
    p.add_argument('--profile',required=True);p.add_argument('--smoke',required=True);p.add_argument('--acceptance',required=True)
    p.add_argument('--budget-seconds',type=int,default=0);p.add_argument('--history')
    p=sub.add_parser('inspect-verification',help='check materialized verifier inputs, never design PASS')
    p.add_argument('package')
    p=sub.add_parser('execute-formal',help='bound candidate Formal; default NOT_RUN, Linux and separate execution authorization required')
    for part in ('package','contract','frozen-root','work'):p.add_argument('--'+part,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--image-identity')
    p=sub.add_parser('inspect-formal',help='offline model/property/process structure checks, never certified Formal PASS')
    for part in ('package','contract','result','expected-sha256'):p.add_argument('--'+part,required=True)
    for command in ('verify-next','prepare-verification','review-candidate'):
        p=sub.add_parser(command,help='evidence-bound independent verification handoff; no EDA execution')
        for part in ('profile','smoke','acceptance','result','expected-sha256'):p.add_argument('--'+part,required=True)
        p.add_argument('--budget-seconds',type=int,default=0,help='unspent native verification seconds, excluding setup/billing')
        if command=='prepare-verification':p.add_argument('--output',required=True)
        else:
            p.add_argument('--formal-result');p.add_argument('--formal-sha256')
            if command=='review-candidate':
                for part in ('profile','smoke','acceptance'):p.add_argument('--after-'+part)
                p.add_argument('--verification-package');p.add_argument('--formal-contract')
    p=sub.add_parser('evaluate',help='independently compare before/after evidence; never trusts policy success')
    for side in ('before','after'):
        for part in ('profile','smoke','acceptance'):p.add_argument('--'+side+'-'+part,required=True)
    p.add_argument('--candidate',required=True)
    p=sub.add_parser('prepare-action',help='write an exclusive isolated synthesis package; never executes EDA')
    for part in ('profile','smoke','acceptance','candidate','output'):p.add_argument('--'+part,required=True)
    p=sub.add_parser('execute-action',help='native Linux isolated synthesis; default NOT_RUN, needs separate authorization')
    for part in ('package','frozen-root','work'):p.add_argument('--'+part,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--image-identity',help='minimal host Docker image identity record, required for execution')
    p=sub.add_parser('seal-action',help='seal only allowlisted saved action outputs; no execution')
    for part in ('package','work','output'):p.add_argument('--'+part,required=True)
    p=sub.add_parser('inspect-action',help='inspect saved phase evidence and bounded outcome history; no adoption')
    p.add_argument('artifact');p.add_argument('--expected-sha256');p.add_argument('--expected-candidate')
    p=sub.add_parser('advance-action',help='update bounded history and pending verification from pinned result evidence; no execution')
    for part in ('profile','smoke','acceptance','result','expected-sha256'):p.add_argument('--'+part,required=True)
    p.add_argument('--budget-seconds',type=int,default=0);p.add_argument('--history')
    args=parser.parse_args()
    try:
        if args.command=='inspect-io-coverage':
            _,sdc=read(args.sdc,2*1024*1024);_,ports=read(args.ports,2*1024*1024)
            state=inspect_io_coverage(sdc,ports);rc=2 if state['observation']=='HOLD_PROFILE_OR_INVENTORY' else 0
        elif args.command=='prepare-hold-script':
            from .execution import _unlinked
            script=build_hold_script();target=_unlinked(args.output)
            with target.open('xb') as stream:stream.write(script)
            state={'execution_status':'NOT_RUN','script_sha256':hashlib.sha256(script).hexdigest(),
                   'initialization_sha256':STA_PREFIX_SHA256,'native_integration':'NOT_RUN',
                   'requires':['fresh mounted final inputs','frozen source/library/binary/OCI identity admission','process timeout/resource limits','separate execution authorization'],'scope':'fixed GCD/Nangate45 native STA recipe only'};rc=0
        elif args.command=='observe-hold':
            raw,text=read(args.log,16*1024*1024);state=observe_hold(args.return_code,text)
            state['raw_log_sha256']=hashlib.sha256(raw).hexdigest()
            rc=0 if state['observation'] in ('NEGATIVE_HOLD_REPORTED','NO_NEGATIVE_HOLD_REPORTED') else 2
        elif args.command=='explain-timing':
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            state=explain_timing(case);rc=0 if state['contribution_gate']=='PASS_ARITHMETIC_CHECK' else 2
        elif args.command=='decide':
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            after_args=(args.after_profile,args.after_smoke,args.after_acceptance)
            if any(after_args) and not all(after_args):raise ValueError('complete after profile/Smoke/acceptance inputs required')
            after=load_case(read_json(args.after_profile),args.after_smoke,args.after_acceptance) if all(after_args) else None
            state=decide(case,args.budget_seconds,args.result,args.expected_sha256,args.formal_result,args.formal_sha256,args.verification_package,args.formal_contract,after,read_json(args.action_history) if args.action_history else None)
            rc=2 if state['next_action']=='HOLD_EVIDENCE' else 0
        elif args.command=='diagnose':
            state=diagnose(args.artifact,args.expected_sha256)
            rc=0 if state['evidence_gate']=='PASS' and state['analysis_gate']=='PASS' else 2
        elif args.command=='inspect-formal':
            state=inspect_formal(args.package,args.contract,args.result,args.expected_sha256)
            rc=0 if state['scope_structure_gate']=='PASS_STATIC_CHECKS' else 2
        elif args.command=='execute-formal':
            state=execute_formal(args.package,args.contract,args.frozen_root,args.work,args.execute,
                                 read_json(args.image_identity,65536) if args.execute and args.image_identity else None)
            rc=0 if state['status'] in ('NOT_RUN','UNBOUNDED_PROOF_REPORTED') else 2
        elif args.command=='inspect-verification':
            state=verify_verification_package(args.package);rc=0
        elif args.command in ('verify-next','prepare-verification','review-candidate'):
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            if args.command=='review-candidate':
                after_args=(args.after_profile,args.after_smoke,args.after_acceptance)
                if any(after_args) and not all(after_args):raise ValueError('complete after profile/Smoke/acceptance inputs required')
                after=load_case(read_json(args.after_profile),args.after_smoke,args.after_acceptance) if all(after_args) else None
                state=review_candidate(case,args.result,args.expected_sha256,args.budget_seconds,args.formal_result,args.formal_sha256,after,args.verification_package,args.formal_contract)
            elif args.command=='prepare-verification':
                state=prepare_verification(case,args.result,args.expected_sha256,args.output,args.budget_seconds)
            else:
                subject=load_subject(case,args.result,args.expected_sha256)
                state=plan_verification(subject,args.budget_seconds,args.formal_result,args.formal_sha256)
            rc=2 if state.get('decision')=='HOLD_VERIFIER_EVIDENCE' or state.get('candidate_status')=='EVIDENCE_HOLD' else 0
        elif args.command=='advance-action':
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            state=advance_action(case,args.result,args.expected_sha256,args.budget_seconds,read_json(args.history) if args.history else [])
            rc=2 if state['observation']['evidence_gate']=='FAIL' else 0
        elif args.command=='seal-action':
            state=seal_action(args.package,args.work,args.output);rc=0
        elif args.command=='inspect-action':
            state=inspect_action(args.artifact,args.expected_sha256,args.expected_candidate)
            rc=2 if state['evidence_gate']=='FAIL' else 0
        elif args.command=='prepare-action':
            case=load_case(read_json(args.profile),args.smoke,args.acceptance)
            state=prepare_action(case,read_json(args.candidate),args.output);rc=0
        elif args.command=='execute-action':
            state=execute_action(args.package,args.frozen_root,args.work,args.execute,
                                 read_json(args.image_identity,65536) if args.execute and args.image_identity else None)
            rc=0 if state['status'] in ('NOT_RUN','SYNTHESIS_COMPLETED') else 2
        elif args.command=='plan':
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
