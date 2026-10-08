"""Bounded tool observation. Never classifies SIGILL as proven AVX-512."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

LIMIT = 8 * 1024 * 1024

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def signal_name(rc):
    if rc is None or rc >= 0: return None
    try: return signal.Signals(-rc).name
    except ValueError: return "SIGNAL_"+str(-rc)

def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(LIMIT,LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))

def observe(argv, directory, limit=LIMIT, seconds=150, tracing=True, forward=True):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    resolved=Path(shutil.which(argv[0]) or argv[0]).resolve(strict=True)
    record={"original_argv":argv, "resolved_executable":str(resolved),
            "executable_sha256":sha(resolved), "core_limit_bytes":0,
            "stream_limit_bytes":limit, "timeout_seconds":seconds,
            "AVX512_HYPOTHESIS":"UNPROVEN_HOLD", "fault_PC":None,"opcode":None}
    reader=shutil.which("readelf")
    if reader and os.name=="posix":
        try:
            note=subprocess.run([reader,"-n",str(resolved)],capture_output=True,
                timeout=5,preexec_fn=limits)
            raw=note.stdout[:limit]
            (directory/"executable.notes").write_bytes(raw)
            import re
            match=re.search(rb"Build ID:\s*(\w+)",raw)
            record["build_id"]=match[1].decode() if match else "NOT_AVAILABLE"
        except (OSError,subprocess.TimeoutExpired): record["build_id"]="NOT_AVAILABLE"
    else: record["build_id"]="NOT_AVAILABLE"
    command=list(argv)
    tracer=shutil.which("strace") if tracing and os.name=="posix" else None
    trace_ready=False
    if tracer:
        try:
            probe=subprocess.run([tracer,"-qq","-o",str(directory/"strace-probe.log"),"/bin/true"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,preexec_fn=limits)
            trace_ready=probe.returncode==0
        except (OSError,subprocess.TimeoutExpired): pass
    record["process_trace_status"]="ENABLED" if trace_ready else "NOT_AVAILABLE_OR_DENIED_HOLD"
    if trace_ready:
        record["strace_sha256"]=sha(tracer)
        command=[tracer,"-ff","-qq","-s","128","-e",
            "trace=execve,clone,fork,vfork,wait4,waitid,exit_group","-e","signal=SIGILL",
            "-o",str(directory/"process.trace"),*argv]
    record["observed_argv"]=command
    start=time.monotonic()
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        start_new_session=os.name=="posix",preexec_fn=limits if os.name=="posix" else None)
    record["pid"]=p.pid
    record["pid_kind"]="STRACE_PID" if trace_ready else "DIRECT_CHILD_PID"
    counts=[0,0]; saved=[0,0]; errors=[]
    def pump(stream,name,index,destination):
        try:
            with (directory/name).open("wb") as out:
                while True:
                    b=stream.read(4096)
                    if not b: break
                    counts[index]+=len(b)
                    keep=b[:max(0,limit-saved[index])]
                    if keep:
                        out.write(keep); saved[index]+=len(keep)
                        if forward: destination.buffer.write(keep); destination.flush()
        except Exception as e: errors.append(type(e).__name__)
    threads=[threading.Thread(target=pump,args=(p.stdout,"formal.stdout",0,sys.stdout)),
             threading.Thread(target=pump,args=(p.stderr,"formal.stderr",1,sys.stderr))]
    for t in threads:t.start()
    timed_out=False
    try: rc=p.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        timed_out=True
        if os.name=="posix": os.killpg(p.pid,signal.SIGKILL)
        else: p.kill()
        p.wait(); rc=124
    for t in threads:t.join(timeout=5)
    if any(t.is_alive() for t in threads):
        if os.name=="posix":
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        for t in threads:t.join(timeout=5)
        errors.append("STREAM_DRAIN_TIMEOUT")
        if rc==0: rc=125
    if errors and rc==0: rc=125
    p.stdout.close()
    p.stderr.close()
    record.update(actual_returncode=rc, signal=signal_name(rc), timed_out=timed_out,
        limit_interference_possible=timed_out or signal_name(rc) in ("SIGXFSZ","SIGXCPU","SIGKILL"),
        runtime_seconds=time.monotonic()-start, stream_bytes=counts, saved_stream_bytes=saved,
        truncated=any(n>limit for n in counts), recorder_errors=errors)
    (directory/"process.json").write_text(json.dumps(record,indent=2)+"\n")
    return rc

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("command",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    cmd=args.command[1:] if args.command[:1]==["--"] else args.command
    if len(cmd)!=3 or cmd[1]!="--config": parser.error("only executable --config public.yml is permitted")
    if os.name=="posix": limits()
    rc=observe(cmd,args.output)
    # Preserve signal termination for Tcl; process.json names the original child PID.
    if rc<0 and os.name=="posix":
        signal.signal(-rc,signal.SIG_DFL)
        os.kill(os.getpid(),-rc)
    return rc
if __name__=="__main__": sys.exit(main())
