import glob
import json
import os

# latest jsonl in datalog
dl = os.path.expanduser(r"~\.atomcode\datalog")
files = sorted(glob.glob(os.path.join(dl, "**", "*.jsonl"), recursive=True),
               key=os.path.getmtime, reverse=True)
f = files[0]
print("file:", f)
line = open(f, encoding="utf-8").readline()
data = json.loads(line)
print("estimated_tokens:", data.get("estimated_tokens"))
print("tool_count:", data.get("tool_count"))
print("message_count:", data.get("message_count"))
print("=" * 60)
total = 0
for i, m in enumerate(data["messages"]):
    text = m.get("text") or ""
    role = m.get("role")
    total += len(text)
    head = text[:160].replace("\n", " ")
    print(f"\n[msg {i} role={role} chars={len(text)}] {head}")

print("\n" + "=" * 60)
print("TOTAL system+user text chars:", total, "≈", round(total / 4), "tokens")

# what's in the system prompt? find section markers
all_sys = "\n".join(m.get("text") or "" for m in data["messages"] if m.get("role") == "System")
for marker in ["skill", "SKILL", "tools", "Tools", "AGENTS.md", "CLAUDE.md", "ATOMCODE.md", "MEMORY", "## ", "bash", "MCP"]:
    cnt = all_sys.count(marker)
    if cnt:
        print(f"  marker '{marker}': {cnt} occurrences")
