"""Drain input fully while recording at most 8 MiB; no hidden deadlock on truncation."""
import json
from pathlib import Path
import sys
limit=8*1024*1024
target=Path(sys.argv[1]); total=0; saved=0
with target.open("xb") as out:
    while True:
        b=sys.stdin.buffer.read(65536)
        if not b:break
        total+=len(b); keep=b[:max(0,limit-saved)]
        out.write(keep);saved+=len(keep)
target.with_suffix(".size.json").write_text(json.dumps({"bytes_seen":total,"bytes_saved":saved,"truncated":total>limit})+"\n")
