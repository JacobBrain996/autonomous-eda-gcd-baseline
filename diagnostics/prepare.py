"""Identity validation and fresh ephemeral-runner input restoration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import zipfile
from observe import sha

COMMIT="3a964e13f11a4e435aac01ffa14db0a7d2853720"
IMAGE="openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9"
ZIP_SHA="9caa14593d6c9db005db2807d8fddd7558c183ccbdc2b9f9faedf4cd1f4481d5"
INPUTS={
 "4_before_rsz_lec.v":"4bf624505d1e079f70d2ad989b7ab039412f5453ba5787f9de715cad793107a3",
 "4_after_rsz_lec.v":"4dfd2da384aa535c585f5267bc5195bcbef9385af858f1a87a7da95e319c0019"}
def restore(archive,destination):
    assert sha(archive)==ZIP_SHA,"HOLD: not the authoritative Run 1 ZIP"
    destination=Path(destination); destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        m=json.loads(z.read("manifest.json"))
        assert m["orfs_commit_actual"]==COMMIT and IMAGE in m["container_repo_digests_actual"]
        assert m["design"]=="gcd" and m["platform"]=="nangate45"
        for name,h in INPUTS.items():
            b=z.read("raw-logs/orfs-results/"+name)
            assert hashlib.sha256(b).hexdigest()==h
            with (destination/name).open("xb") as f:f.write(b)
    (destination/"restored-inputs.json").write_text(json.dumps(INPUTS,indent=2)+"\n")

def effective(args):
    out=Path("/diagnostic-work")
    payload={"LEC_CHECK":args.lec,"SEC_CHECK":args.sec,
        "KEPLER_FORMAL_EXE":args.executable,"LIB_FILES":args.libs.split(),
        "REMOVE_LIBS_FOR_LEC":args.remove_libs.split()}
    assert payload["LEC_CHECK"]=="1","HOLD: effective LEC is not 1"
    assert payload["SEC_CHECK"]=="0","HOLD: unexpected SEC setting"
    exe=Path(args.executable).resolve(strict=True)
    payload["executable_realpath"]=str(exe);payload["executable_sha256"]=sha(exe)
    (out/"effective.json").write_text(json.dumps(payload,indent=2)+"\n")

def driver():
    info=json.loads(Path("/diagnostic-work/effective.json").read_text())
    env=dict(os.environ)
    env.update({k:info[k] for k in ("LEC_CHECK","SEC_CHECK","KEPLER_FORMAL_EXE")})
    env.update(DIAG_DIR="/diagnostic-work", SCRIPTS_DIR="/OpenROAD-flow-scripts/flow/scripts",
        OBJECTS_DIR="/diagnostic-work/objects", RESULTS_DIR="/diagnostic-work/results",
        LOG_DIR="/diagnostic-work/logs", LIB_FILES=" ".join(info["LIB_FILES"]),
        REMOVE_LIBS_FOR_LEC=" ".join(info["REMOVE_LIBS_FOR_LEC"]))
    for name in ("objects","results","logs"):Path("/diagnostic-work",name).mkdir(exist_ok=True)
    for name in INPUTS:
        target=Path("/diagnostic-work/results",name)
        target.write_bytes(Path("/run1-inputs",name).read_bytes())
        assert sha(target)==INPUTS[name]
    hooks={p.name:sha(p) for p in Path("/diagnostic").iterdir() if p.is_file()}
    grep_path=shutil.which("grep")
    Path("/diagnostic-work/hooks.json").write_text(json.dumps({"files":hooks,
        "python_executable":sys.executable,"python_sha256":sha(sys.executable),
        "python_version":sys.version,"openroad_sha256":sha("/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"),
        "grep_path":grep_path,"grep_sha256":sha(grep_path) if grep_path else None,
        "entrypoint":"/diagnostic/replay.tcl"},indent=2)+"\n")
    rc=subprocess.call(["/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
        "-no_init","-exit","/diagnostic/replay.tcl"],env=env)
    Path("/diagnostic-work/replay-status.json").write_text(json.dumps({
        "openroad_returncode":rc,"ROOT_CAUSE_STATUS":"PARTIALLY_LOCALIZED_HOLD",
        "AVX512_HYPOTHESIS":"UNPROVEN_HOLD","FORMAL_EQUIVALENCE_GATE":
        "PASS_LEC_REPLAY_ONLY" if rc==0 else "FAIL_OR_DIAGNOSTIC_HOLD",
        "scope":"reconstructed local LEC; not physical baseline"})+"\n")
    return rc

def export():
    root=Path("/diagnostic-work");dest=Path("/diagnostic-out")
    total=0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():continue
        assert p.stat().st_size<=8*1024*1024,"diagnostic per-file cap exceeded"
        total+=p.stat().st_size
        assert total<=128*1024*1024,"diagnostic total cap exceeded"
        q=dest/p.relative_to(root);q.parent.mkdir(parents=True,exist_ok=True)
        with q.open("xb") as f:f.write(p.read_bytes())

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    subs=parser.add_subparsers(dest="mode",required=True)
    r=subs.add_parser("restore");r.add_argument("archive");r.add_argument("destination")
    e=subs.add_parser("effective")
    for arg in ("lec","sec","executable","libs","remove-libs"):e.add_argument("--"+arg,required=True)
    subs.add_parser("driver");subs.add_parser("export")
    args=parser.parse_args()
    if args.mode=="restore":restore(args.archive,args.destination)
    elif args.mode=="effective":effective(args)
    elif args.mode=="driver":raise SystemExit(driver())
    else:export()
