# pi-bridge

Remote command bridge for my own Raspberry Pi (DietPi). The Pi makes outbound connections only (no port forwarding, no listener). It subscribes to a private [ntfy](https://ntfy.sh) topic derived from a secret token, runs **only HMAC-signed, fresh commands as root**, and posts stdout/stderr/exit code back.

## Install (on the Pi, as root)
    wget -O pb.sh https://raw.githubusercontent.com/Greenisus1/pi-bridge/main/install.sh
    bash pb.sh YOUR_TOKEN

The token is never stored in this repo. It lives in `/etc/pi-bridge/config.json` (chmod 600).

## Use
    PIBRIDGE_TOKEN=... python3 send.py 'uptime'
    PIBRIDGE_TOKEN=... python3 send.py --status

## Notes
- Commands run as **root**. Anyone with the token can run anything on the Pi. Keep it secret.
- Commands expire after 10 minutes and each id runs once (replay protection).
- Output passes through the ntfy.sh server; the topic name is unguessable but output is not encrypted. Avoid printing secrets.
- Audit log: `/var/log/pi-bridge.log`. Manage: `pibridge logs|stop|start|uninstall`. Auto-starts on boot, restarts on failure.
