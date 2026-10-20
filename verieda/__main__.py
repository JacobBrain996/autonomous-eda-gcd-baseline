import argparse,json
from .evidence import inspect

def main():
    parser=argparse.ArgumentParser(prog='python -m verieda')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inspect',help='independently audit an ORFS artifact ZIP or directory')
    p.add_argument('artifact');p.add_argument('--expect',help='external experiment_identity.json')
    p.add_argument('--expected-sha256',help='trusted SHA256 of the original ZIP')
    args=parser.parse_args()
    state=inspect(args.artifact,args.expect,args.expected_sha256)
    print(json.dumps(state,indent=2,ensure_ascii=True,allow_nan=False))
    return 2 if state['gates']['evidence']=='FAIL' else 0

if __name__=='__main__':raise SystemExit(main())
