import json
import socket
import time

body = json.dumps({
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Count from 1 to 40, one number per line, nothing else."}],
    "stream": True,
}).encode()

s = socket.create_connection(("127.0.0.1", 13458), timeout=10)
s.settimeout(300)
s.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body))
s.sendall(body)

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
print("first content chunk: %.2fs" % (first if first else -1))
print("done: %.2fs" % (done if done else -1))
