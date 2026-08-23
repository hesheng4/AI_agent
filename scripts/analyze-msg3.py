import glob
import json
import os

dl = os.path.expanduser(r"~\.atomcode\datalog")
files = sorted(glob.glob(os.path.join(dl, "**", "*.jsonl"), recursive=True),
               key=os.path.getmtime, reverse=True)
f = files[0]
line = open(f, encoding="utf-8").readline()
data = json.loads(line)

# find the big User message (msg 3 = our flattened prompt)
for i, m in enumerate(data["messages"]):
    text = m.get("text") or ""
    if m.get("role") == "User" and len(text) > 5000:
        print(f"=== msg {i} role=User chars={len(text)} ===")
        # print section headers / structural markers
        lines = text.split("\n")
        headers = []
        for j, ln in enumerate(lines):
            if ln.startswith("#") or ln.startswith("<") or ln.startswith("==="):
                headers.append((j, ln[:100]))
        print("structural lines (first 60):")
        for j, h in headers[:60]:
            print(f"  [{j}] {h}")
        # also show first 800 chars and last 800 chars
        print("\n--- HEAD 800 ---")
        print(text[:800])
        print("\n--- TAIL 800 ---")
        print(text[-800:])
        break
