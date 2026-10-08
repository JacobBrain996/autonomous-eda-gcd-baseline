"""Collect actual measurements only; missing evidence can never create a PASS."""
import hashlib
import json
import math
import re
import shutil
from pathlib import Path

E = Path("evidence")
for folder in ("environment", "raw-logs", "gds", "failure", "status"):
    (E / folder).mkdir(parents=True, exist_ok=True)
identity = json.loads(Path("experiment_identity.json").read_text())
flow = Path("orfs/flow")
for folder in ("logs", "reports", "results"):
    source = flow / folder / "nangate45/gcd/base"
    if source.exists():
        shutil.copytree(source, E / "raw-logs" / ("orfs-" + folder), dirs_exist_ok=True)
gds_source = flow / "results/nangate45/gcd/base/6_final.gds"
if gds_source.is_file():
    shutil.copy2(gds_source, E / "gds/6_final.gds")

def write(name, payload):
    (E / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def read_rc(name):
    p = E / "status" / name
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None

def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}

def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

logs = flow / "logs/nangate45/gcd/base"
final = read_json(logs / "6_report.json")
def measured(key, final_only=True):
    sources = [logs / "6_report.json"] if final_only else sorted(logs.glob("*.json"))
    hits = []
    for path in sources:
        payload = final if final_only else read_json(path)
        if not isinstance(payload, dict):
            continue
        value = payload.get(key)
        if numeric(value):
            hits.append((value, path.as_posix(), key))
    if not hits or len({x[0] for x in hits}) != 1:
        return {"value": None, "status": "NOT_AVAILABLE", "reason": "missing, nonnumeric, or conflicting source"}
    return {"value": hits[0][0], "status": "AVAILABLE",
            "sources": [{"path": p, "key": k} for _, p, k in hits]}

metrics = {
    "worst_setup_slack": measured("finish__timing__setup__ws"),
    "TNS": measured("finish__timing__setup__tns"),
    "worst_hold_slack": measured("finish__timing__hold__ws"),
    "hold_TNS": measured("finish__timing__hold__tns"),
    "area": measured("finish__design__instance__area"),
    "DRC": measured("detailedroute__route__drc_errors", False),
}
ws = metrics["worst_setup_slack"]
metrics["WNS"] = dict(ws, value=min(0, ws["value"])) if ws["status"] == "AVAILABLE" else dict(ws)
gds = E / "gds/6_final.gds"
metrics["GDS_PATH"] = {"value": "gds/6_final.gds" if gds.is_file() else None,
                       "status": "AVAILABLE" if gds.is_file() else "NOT_AVAILABLE"}
write("metrics.json", metrics)
sim_rc = read_rc("simulation-return-code.txt")
physical_rc = read_rc("physical-return-code.txt")
tool_rc = read_rc("core-tool-return-code.txt")
gds_rc = read_rc("gds-read-return-code.txt")
illegal = any(rc == 132 for rc in (sim_rc, physical_rc, tool_rc, gds_rc))
for path in (E / "raw-logs").rglob("*.log"):
    if re.search(r"illegal instruction|SIGILL|exit(?:ed)?(?: with)?(?: code)?[ =:]+132",
                 path.read_text(errors="replace"), re.I):
        illegal = True
tool_log = E / "environment/tool-versions.txt"
if tool_log.exists() and re.search(r"illegal instruction|SIGILL", tool_log.read_text(errors="replace"), re.I):
    illegal = True
write("runtime.json", {
    "return_code": physical_rc, "return_code_status": "AVAILABLE" if physical_rc is not None else "NOT_AVAILABLE",
    "physical_runtime_seconds": read_rc("physical-runtime-seconds.txt"),
    "simulation_return_code": sim_rc, "simulation_runtime_seconds": read_rc("simulation-runtime-seconds.txt"),
    "cpu_instruction_incompatible": illegal,
    "failure_class": "CPU_INSTRUCTION_INCOMPATIBLE" if illegal else "SEE_RAW_LOGS",
})
head_file = E / "environment/orfs-head.txt"
head = head_file.read_text().strip() if head_file.is_file() else None
inspect_path = E / "environment/image-inspect.json"
inspection = read_json(inspect_path)
image = inspection[0] if isinstance(inspection, list) and inspection else {}
identity_ok = (head == identity["orfs_commit"]
               and identity["orfs_image"] in image.get("RepoDigests", [])
               and image.get("Architecture") == "amd64" and image.get("Os") == "linux")
write("manifest.json", {
    **identity, "orfs_commit_actual": head,
    "container_repo_digests_actual": image.get("RepoDigests", []),
    "container_image_id": image.get("Id"), "image_architecture_actual": image.get("Architecture"),
    "testbench_sha256_actual": hashlib.sha256(Path("tests/tb_gcd.sv").read_bytes()).hexdigest(),
    "physical_return_code": physical_rc, "simulation_return_code": sim_rc,
    "tool_versions_path": "environment/tool-versions.txt",
    "scope": "public ORFS gcd/nangate45 only; no foundry DRC/LVS signoff",
})
gates = {
    "RTL_SIMULATION_GATE": "NOT_RUN" if sim_rc is None else ("PASS" if sim_rc == 0 else "FAIL"),
    "PHYSICAL_FLOW_GATE": "NOT_RUN" if physical_rc is None else ("PASS" if physical_rc == 0 else "FAIL"),
    "TIMING_GATE": "NOT_AVAILABLE",
    "ARTIFACT_GATE": "FAIL",
}
timing = [metrics[k] for k in ("worst_setup_slack", "TNS", "worst_hold_slack", "hold_TNS")]
if physical_rc == 0 and all(x["status"] == "AVAILABLE" for x in timing):
    gates["TIMING_GATE"] = "PASS" if all(x["value"] >= 0 for x in timing) else "FAIL"
# Readability, nonempty GDS, final checkpoint, complete measurements and provenance are mandatory.
checkpoint = flow / "results/nangate45/gcd/base/6_final.odb"
complete = all(metrics[k]["status"] == "AVAILABLE" for k in ("WNS", "TNS", "area", "DRC"))
if (identity_ok and tool_rc == 0 and gds_rc == 0 and gds.is_file() and gds.stat().st_size > 0
        and checkpoint.is_file() and checkpoint.stat().st_size > 0 and complete):
    gates["ARTIFACT_GATE"] = "PASS"
if physical_rc == 0 and metrics["DRC"]["status"] == "AVAILABLE" and metrics["DRC"]["value"] != 0:
    gates["PHYSICAL_FLOW_GATE"] = "FAIL"
if physical_rc == 0 and metrics["DRC"]["status"] != "AVAILABLE":
    gates["PHYSICAL_FLOW_GATE"] = "NOT_AVAILABLE"
write("gates.json", gates)
write("failure/report.json", {
    "gates": gates, "cpu_instruction_incompatible": illegal,
    "missing_measurements": [k for k, v in metrics.items() if v["status"] != "AVAILABLE"],
    "image_and_source_identity_match": identity_ok,
    "artifact_upload_status": "EVALUATED_BY_WORKFLOW_AFTER_UPLOAD",
    "timing_scope": "final setup and hold slack/TNS only; coverage and corners require artifact review",
    "CLOUD_BASELINE_RUN1": "NOT_PROMOTED_BEFORE_DOWNLOADED_ARTIFACT_AUDIT",
})
paths = sorted(p for p in E.rglob("*") if p.is_file() and p.name not in ("SHA256SUMS.txt", "file-sizes.json"))
write("file-sizes.json", [{"path": p.relative_to(E).as_posix(), "bytes": p.stat().st_size} for p in paths])
# GNU sha256sum compatible; spaces stay part of the path. Escape newline/backslash names.
paths = sorted(p for p in E.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
lines = []
for path in paths:
    name = path.relative_to(E).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    escaped = "\\" in name or "\n" in name
    name = name.replace("\\", "\\\\").replace("\n", "\\n")
    lines.append(("\\" if escaped else "") + digest + "  " + name)
(E / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(gates, indent=2))
