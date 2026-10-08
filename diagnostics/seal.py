"""Seal only diagnostic artifacts. Never include the downloaded input ZIP."""
import json
from pathlib import Path
from observe import sha

SINGLE=8*1024*1024
TOTAL=144*1024*1024
def inventory(files,root,single=SINGLE,total=TOTAL):
    size=sum(p.stat().st_size for p in files)
    valid=size<=total and all(not p.is_symlink() and p.stat().st_size<=single for p in files)
    return {"bytes":size,"cap_bytes":total,"within_limits":valid,
        "files":[{"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,
                  "sha256":sha(p) if valid else None} for p in files]}

def main():
    root=Path("evidence");diag=root/"cts-lec-diagnostic"
    files=[]
    for folder in (diag/"output",root/"environment"):
        if folder.exists():files.extend(p for p in folder.rglob("*") if p.is_file())
    for name in ("container.log","container.size.json","container-return-code.txt",
                 "image-inspect.json","artifact-source.json","cpu-comparison.json"):
        p=diag/name
        if p.is_file():files.append(p)
    data=inventory(sorted(files),root)
    data.update(scope="CTS_POST_REPAIR_LEC_REPLAY_ONLY",AVX512_HYPOTHESIS="UNPROVEN_HOLD",
                CLOUD_BASELINE_RUN1="FAIL",CLOUD_BASELINE_RUN2="NOT_RUN")
    diag.mkdir(parents=True,exist_ok=True)
    (diag/"diagnostic-artifact-manifest.json").write_text(json.dumps(data,indent=2)+"\n")
    assert data["within_limits"],"HOLD: diagnostic artifact budget exceeded"
if __name__=="__main__":main()
