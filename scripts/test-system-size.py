# Measure prompt-token impact of the harness-sized system message (before/after truncation).
import json
import time
import urllib.request

# Synthetic harness-like system message (~15k chars of catalog-ish noise)
big_system = "# Harness System Prompt\n" + ("- Tool description line with schema and examples for tool_%d, parameters a b c d e f g h i j\n" % (1)) * 0
big_system = "You are an AI agent. Here is your tool catalog:\n" + "\n".join(
    "Tool %d: function %d(args: {a,b,c,d,e,f,g,h,i,j}) -> {result}, description line with many words to simulate a real tool schema block." % (i, i)
    for i in range(120)
) + "\n" + ("- extra skill description line for skill %d with trigger words and examples\n" * 0)
big_system = "You are an AI agent.\n" + "\n".join(
    "Tool %d description: does operation %d with parameters alpha beta gamma delta epsilon and returns a result object with fields one two three four five." % (i, i)
    for i in range(150)
)
print("system chars:", len(big_system))

body = json.dumps({
    "model": "deepseek-v4-flash",
    "messages": [
        {"role": "system", "content": big_system},
        {"role": "user", "content": "Reply with exactly: HI"},
    ],
    "stream": False,
}).encode()
req = urllib.request.Request("http://127.0.0.1:13458/v1/chat/completions",
                             data=body, headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=120) as r:
    resp = json.loads(r.read().decode())
dt = time.time() - t0
print("usage:", resp.get("usage"))
print("wall time: %.2fs" % dt)
print("reply:", resp["choices"][0]["message"]["content"][:80])
