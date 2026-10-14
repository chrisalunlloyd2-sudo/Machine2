"""Builds gap_feed.jsonl: Aria gaps -> py4qwhip synthesis-job inputs. Read-only on the vault."""
import json, os, sys
V = r"C:\Viper"
OUT = os.path.join(V, "projects", "py4qwhip", "gap_feed.jsonl")
last = {}
for l in open(os.path.join(V, "aria_vault", "gaps.jsonl"), encoding="utf-8"):
    if l.strip():
        r = json.loads(l); last[r["id"]] = r
def on_disk(name):
    hits = []
    for root in (V + r"\scripts", V + r"\projects", V + r"\databases\aegis"):
        for d, ds, fs in os.walk(root):
            ds[:] = [x for x in ds if x not in (".git", "__pycache__", "node_modules", "site-packages")]
            if name + ".py" in fs: hits.append(os.path.join(d, name + ".py"))
            if len(hits) > 2: return hits
    return hits
n = 0
with open(OUT, "w", encoding="utf-8") as o:
    for r in last.values():
        if r.get("event") != "open" or r.get("kind") not in ("MODULE_MISSING", "IMPORT_ELSEWHERE"): continue
        found = on_disk(r["name"])
        job = {"job": "synthesize_module" if not found else "resolve_path", "gap_id": r["id"], "kind": r["kind"],
               "module": r["name"], "imported_by": r.get("imported_by", []), "found_on_disk": found,
               "expect": "import resolves without sys.path tricks"}
        o.write(json.dumps(job) + "\n"); n += 1
print(n, "jobs ->", OUT)
