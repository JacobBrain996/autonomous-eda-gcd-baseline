"""Fetch only the declared Run 1 artifact; never print credentials or persist tokens."""
import json
from pathlib import Path
import subprocess
from prepare import ZIP_SHA
from observe import sha

repo="JacobBrain996/autonomous-eda-gcd-baseline"
run="37756530984"
root=Path("evidence/cts-lec-diagnostic");root.mkdir(parents=True,exist_ok=True)
result=subprocess.run(["gh","api",f"repos/{repo}/actions/runs/{run}/artifacts?per_page=100"],
    capture_output=True,check=True,timeout=30)
payload=json.loads(result.stdout)
artifacts=[a for a in payload["artifacts"] if a["name"].startswith("orfs-gcd-baseline") and not a["expired"]]
assert len(artifacts)==1,"HOLD: missing/ambiguous/expired Run 1 artifact"
a=artifacts[0]
assert a["size_in_bytes"]<=8*1024*1024,"HOLD: unexpected archive size"
with (root/"run1.zip").open("xb") as out:
    child=subprocess.Popen(["gh","api",f"repos/{repo}/actions/artifacts/{a['id']}/zip"],
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    count=0
    try:
        while True:
            chunk=child.stdout.read(65536)
            if not chunk:break
            count+=len(chunk)
            if count>8*1024*1024:child.kill();raise RuntimeError("archive download cap")
            out.write(chunk)
        assert child.wait(timeout=30)==0,"artifact download failed"
    finally:
        if child.poll() is None:child.kill();child.wait()
assert sha(root/"run1.zip")==ZIP_SHA,"HOLD: archive does not match authoritative Run 1 ZIP"
(root/"artifact-source.json").write_text(json.dumps({"run_id":run,"artifact_id":a["id"],
    "artifact_name":a["name"],"zip_sha256":ZIP_SHA},indent=2)+"\n")
