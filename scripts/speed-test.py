# Realistic speed measurement + prompt-size investigation.
import json
import socket
import time
import urllib.request


# 1) a realistic coding-ish prompt through the bridge (stream=true), measure first/last token
def measure_stream(prompt_text, effort=None):
    body = {"model": "deepseek-v4-flash",
            "messages": [{"role": "user", "content": prompt_text}],
            "stream": True}
    if effort:
        body["reasoning_effort"] = effort
    data = json.dumps(body).encode()
    s = socket.create_connection(("127.0.0.1", 13458), timeout=10)
    s.settimeout(300)
    s.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(data))
    s.sendall(data)
    t0 = time.time()
    buf = b""
    first = None
    done = None
    marker = b'"delta": {"content":'
    while True:
        try:
            c = s.recv(8192)
        except Exception:
            break
        if not c:
            break
        buf += c
        if first is None and marker in buf:
            first = time.time() - t0
        if b"data: [DONE]" in buf:
            done = time.time() - t0
            break
    s.close()
    return first, done

p = "Explain in 3 sentences what a Python decorator is."
f, d = measure_stream(p)
print("realistic prompt: first=%.2fs done=%.2fs" % (f or -1, d or -1))

# 2) prompt size the daemon actually sends (from a non-stream call usage)
body = json.dumps({"model": "deepseek-v4-flash",
                   "messages": [{"role": "user", "content": "hi"}],
                   "stream": False}).encode()
req = urllib.request.Request("http://127.0.0.1:13458/v1/chat/completions",
                             data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    resp = json.loads(r.read().decode())
usage = resp.get("usage", {})
print("usage for 'hi':", usage)
