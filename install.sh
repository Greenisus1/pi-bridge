#!/bin/bash
# pi-bridge installer. Run as root on the Pi:  bash install.sh <TOKEN>
set -e
TOKEN="$1"
[ -n "$TOKEN" ] || { echo "usage: bash install.sh <TOKEN>"; exit 1; }
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
command -v python3 >/dev/null || { apt-get update && apt-get install -y python3; }
BASE="https://raw.githubusercontent.com/Greenisus1/pi-bridge/main"
mkdir -p /opt/pi-bridge /etc/pi-bridge /var/lib/pi-bridge
wget -q -O /opt/pi-bridge/bridge.py "$BASE/bridge.py"
chmod 700 /opt/pi-bridge/bridge.py
umask 077
printf '{"token": "%s", "server": "https://ntfy.sh"}\n' "$TOKEN" > /etc/pi-bridge/config.json
chmod 600 /etc/pi-bridge/config.json
cat > /etc/systemd/system/pi-bridge.service <<UNIT
[Unit]
Description=pi-bridge remote command agent
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=/usr/bin/python3 /opt/pi-bridge/bridge.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
cat > /usr/local/bin/pibridge <<'CLI'
#!/bin/sh
case "$1" in
 logs) tail -n 50 /var/log/pi-bridge.log;;
 stop) systemctl stop pi-bridge;;
 start) systemctl start pi-bridge;;
 uninstall) systemctl disable --now pi-bridge; rm -rf /opt/pi-bridge /etc/pi-bridge /var/lib/pi-bridge /etc/systemd/system/pi-bridge.service /usr/local/bin/pibridge; echo removed;;
 *) systemctl status pi-bridge --no-pager; echo "usage: pibridge logs|stop|start|uninstall";;
esac
CLI
chmod +x /usr/local/bin/pibridge
systemctl daemon-reload
systemctl enable --now pi-bridge
sleep 2
systemctl is-active pi-bridge && echo "pi-bridge installed and running. Check: pibridge logs"
