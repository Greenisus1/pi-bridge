#!/usr/bin/env python3
"""pi-bridge agent: outbound-only command bridge. Runs on the Pi as root.
Listens on a private ntfy topic (derived from your token), runs only HMAC-signed commands,
posts output back. No inbound ports."""
import os, sys, json, time, hmac, hashlib, base64, subprocess, urllib.request, socket, threading

CFG = os.environ.get("PIBRIDGE_CONFIG", "/etc/pi-bridge/config.json")
STATE = "/var/lib/pi-bridge/state.json"
LOG = "/var/log/pi-bridge.log"
MAX_AGE = 600
CHUNK = 2800

cfg = json.load(open(CFG))
TOKEN = cfg["token"].encode()
SERVER = cfg.get("server", "https://ntfy.sh").rstrip("/")
def topic(kind): return "pb-" + hashlib.sha256(TOKEN + b":" + kind.encode()).hexdigest()[:40]
CMD_T, RES_T = topic("cmd"), topic("res")

def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + m
    try:
        with open(LOG, "a") as f: f.write(line + "\n")
    except Exception: pass
    print(line, flush=True)

def sign(*parts):
    return hmac.new(TOKEN, "|".join(str(p) for p in parts).encode(), hashlib.sha256).hexdigest()

def post(t, obj):
    req = urllib.request.Request(f"{SERVER}/{t}", data=json.dumps(obj).encode(), method="POST")
    for i in range(4):
        try:
            urllib.request.urlopen(req, timeout=20).read(); return True
        except Exception as e:
            log(f"post fail {e}"); time.sleep(2 + i * 3)
    return False

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {"last": None, "seen": []}
def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    s["seen"] = s["seen"][-200:]
    json.dump(s, open(STATE, "w"))

def run(c):
    cid, cmd, to = c["id"], c["cmd"], min(int(c.get("timeout", 120)), 3600)
    log(f"EXEC id={cid} timeout={to} cmd={cmd!r}")
    t0 = time.time()
    try:
        p = subprocess.run(["/bin/bash", "-c", cmd], capture_output=True, timeout=to, cwd="/root")
        code, out = p.returncode, p.stdout + (b"\n--stderr--\n" + p.stderr if p.stderr else b"")
    except subprocess.TimeoutExpired as e:
        code, out = 124, (e.stdout or b"") + b"\n[timed out]"
    except Exception as e:
        code, out = 125, str(e).encode()
    if len(out) > 200000: out = out[:100000] + b"\n[...truncated...]\n" + out[-90000:]
    log(f"DONE id={cid} exit={code} bytes={len(out)} secs={time.time()-t0:.1f}")
    b = base64.b64encode(out).decode()
    parts = [b[i:i + CHUNK] for i in range(0, len(b), CHUNK)] or [""]
    for n, p in enumerate(parts):
        post(RES_T, {"id": cid, "exit": code, "part": n, "parts": len(parts), "data": p})

def handle(raw, st):
    try: c = json.loads(raw)
    except Exception: return
    if not isinstance(c, dict) or "cmd" not in c: return
    try:
        ok = hmac.compare_digest(str(c.get("sig", "")), sign(c["id"], c["ts"], c.get("timeout", 120), c["cmd"]))
    except Exception: ok = False
    if not ok: log("REJECT bad signature"); return
    if abs(time.time() - float(c["ts"])) > MAX_AGE: log(f"REJECT stale id={c['id']}"); return
    if c["id"] in st["seen"]: return
    st["seen"].append(c["id"]); save_state(st)
    threading.Thread(target=run, args=(c,), daemon=True).start()

def heartbeat():
    while True:
        try:
            up = open("/proc/uptime").read().split()[0]
            post(RES_T, {"hb": int(time.time()), "host": socket.gethostname(), "uptime": up})
        except Exception: pass
        time.sleep(600)

def main():
    log(f"pi-bridge start server={SERVER}")
    st = load_state()
    threading.Thread(target=heartbeat, daemon=True).start()
    while True:
        since = st["last"] or str(int(time.time()) - 5)
        try:
            r = urllib.request.urlopen(f"{SERVER}/{CMD_T}/json?since={since}", timeout=120)
            for line in r:
                try: m = json.loads(line)
                except Exception: continue
                if m.get("event") != "message": continue
                st["last"] = m["id"]
                handle(m.get("message", ""), st)
                save_state(st)
        except Exception as e:
            log(f"stream error {e}"); time.sleep(5)
main()
