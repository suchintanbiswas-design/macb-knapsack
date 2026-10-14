#!/usr/bin/env python3
"""Record the machine/software used for a benchmark run (timings are hardware dependent)."""
import json, os, platform, sys, datetime
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
info = dict(
    recorded_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    python=sys.version.split()[0], implementation=platform.python_implementation(),
    platform=platform.platform(), machine=platform.machine(), processor=platform.processor() or "n/a",
    cpu_count=os.cpu_count(),
)
try:
    import matplotlib
    info["matplotlib"] = matplotlib.__version__
except Exception:
    pass
with open(os.path.join(root, "results", "environment.json"), "w") as f:
    json.dump(info, f, indent=2)
print(json.dumps(info, indent=2))
