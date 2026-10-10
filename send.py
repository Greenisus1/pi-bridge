#!/usr/bin/env python3
"""Send one signed command and wait for output. Usage: PIBRIDGE_TOKEN=... python3 send.py [-t secs] 'command'
       python3 send.py --status   (show last heartbeat)"""
import os, sys, json, time, hmac, hashlib, base64, urllib.request, secrets
TOKEN = os.environ["PIBRIDGE_TOKEN"].encode(); SERVER = os.environ.get("PIBRIDGE_SERVER", "https://ntfy.sh")
def topic(k): return "pb-" + hashlib.sha256(TOKEN + b":" + k.encode()).hexdigest()[:40]
def msgs(t, since):
    r = urllib.request.urlopen(f"{SERVER}/{t}/json?poll=1&since={since}", timeout=30)
    return [json.loads(l) for l in r if l.strip()]
a = sys.argv[1:]
if a and a[0] == "--status":
    hb = [json.loads(m["message"]) for m in msgs(topic("res"), "12h") if m.get("event") == "message" and '"hb"' in m["message"]]
    if not hb: print("no heartbeat in last 12h"); sys.exit(1)
    h = hb[-1]; print(f"last heartbeat {int(time.time()-h['hb'])}s ago, host={h['host']}, uptime={h['uptime']}s"); sys.exit(0)
to = 120
if a and a[0] == "-t": to = int(a[1]); a = a[2:]
cmd = " ".join(a); cid = secrets.token_hex(6); ts = int(time.time())
sig = hmac.new(TOKEN, f"{cid}|{ts}|{to}|{cmd}".encode(), hashlib.sha256).hexdigest()
urllib.request.urlopen(urllib.request.Request(f"{SERVER}/{topic('cmd')}", data=json.dumps({"id": cid, "ts": ts, "timeout": to, "cmd": cmd, "sig": sig}).encode(), method="POST"), timeout=20).read()
got = {}; deadline = time.time() + to + 90
while time.time() < deadline:
    time.sleep(3)
    for m in msgs(topic("res"), str(ts - 5)):
        if m.get("event") != "message": continue
        try: d = json.loads(m["message"])
        except Exception: continue
        if d.get("id") == cid: got[d["part"]] = d; tot = d["parts"]
    if got and len(got) == tot:
        sys.stdout.write(base64.b64decode("".join(got[i]["data"] for i in range(tot))).decode(errors="replace"))
        print(f"\n[exit {got[0]['exit']}]"); sys.exit(0)
print("[no result yet - Pi offline or command still running; re-run with --status]"); sys.exit(2)
