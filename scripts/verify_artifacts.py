"""Verify extracted artifact checksums on Windows or Linux, without credentials."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
parser.add_argument("--checksums-only", action="store_true")
args = parser.parse_args()
root = args.directory.resolve()
covered = set()
for raw_line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
    escaped = raw_line.startswith("\\")
    line = raw_line[1:] if escaped else raw_line
    digest, filename = line.split("  ", 1)
    if escaped:
        out = []
        i = 0
        while i < len(filename):
            if filename[i] == "\\":
                i += 1
                assert i < len(filename) and filename[i] in ("\\", "n"), "invalid GNU filename escape"
                out.append("\n" if filename[i] == "n" else "\\")
            else:
                out.append(filename[i])
            i += 1
        filename = "".join(out)
    file = (root / filename).resolve()
    assert file.is_relative_to(root), "checksum path escapes artifact directory"
    assert len(digest) == 64 and hashlib.sha256(file.read_bytes()).hexdigest() == digest, f"hash mismatch: {filename}"
    covered.add(file)
actual = {p.resolve() for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"}
assert actual == covered, "checksum manifest does not cover exactly all payload files"
for item in json.loads((root / "file-sizes.json").read_text()):
    file = (root / item["path"]).resolve()
    assert file.is_relative_to(root) and file.stat().st_size == item["bytes"], "file size mismatch"
if not args.checksums_only:
    manifest = json.loads((root / "manifest.json").read_text())
    expected_commit = "3a964e13f11a4e435aac01ffa14db0a7d2853720"
    expected_image = "openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9"
    assert manifest["orfs_commit"] == expected_commit == manifest["orfs_commit_actual"]
    assert manifest["orfs_image"] == expected_image and expected_image in manifest["container_repo_digests_actual"]
    assert manifest["design"] == "gcd" and manifest["platform"] == "nangate45"
    assert manifest["testbench_sha256_actual"] == manifest["testbench_sha256"]
    assert all(v == "PASS" for v in json.loads((root / "gates.json").read_text()).values()), "one or more runtime gates failed"
print("ARTIFACT_HASH_SIZE_CHECK=PASS")
