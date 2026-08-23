# Verify bridge survives client aborts + effort forwarding end-to-end.
import json
import socket
import time
import urllib.request


def abort_test():
    """Start a stream, read a bit, then abort the connection hard."""
    body = json.dumps({
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": "Write a short paragraph about Python. Then stop."}],
        "stream": True,
        "reasoning_effort": "high",
    }).encode()
    s = socket.create_connection(("127.0.0.1", 13458), timeout=10)
    s.sendall(b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body))
    s.sendall(body)
    s.settimeout(10)
    buf = b""
    got = 0
    try:
        while got < 3000:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            got += len(chunk)
            if b'"delta":{"content"' in buf and b"reasoning" not in buf:
                # got text streaming; abort NOW
                break
        print("abort_test: received", len(buf), "bytes; aborting connection...")
    except Exception as e:
        print("abort_test: recv error", type(e).__name__, e)
    finally:
        try:
            s.close()
        except Exception:
            pass

def health():
    try:
        with urllib.request.urlopen("http://127.0.0.1:13458/health", timeout=5) as r:
            return r.status, r.read().decode()
    except Exception as e:
        return None, str(e)

print("health before:", health())
abort_test()
time.sleep(1)
print("health after abort:", health())

# a normal request must still work afterwards
body = json.dumps({
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Reply with exactly: ALIVE"}],
    "stream": False,
    "reasoning_effort": "low",
}).encode()
req = urllib.request.Request("http://127.0.0.1:13458/v1/chat/completions", data=body,
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode()
        print("post-abort request HTTP", r.status)
        print(raw[:400])
except Exception as e:
    print("post-abort request FAIL", type(e).__name__, e)
