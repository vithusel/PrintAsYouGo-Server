#!/bin/bash

mkdir /root/payg

# Download the latest payg-server.py script
wget -O /root/payg/payg-server.py https://git.vithuselservices.co.uk/vithusel/printasyougo/-/raw/main/Server/payg-server.py?ref_type=heads

# Check if Python3 and Pip are installed, and install if not
if ! command -v python3 &>/dev/null; then
    apt-get update
    apt-get install -y python3
fi
if ! command -v pip3 &>/dev/null; then
    apt-get update
    apt-get install -y python3-pip
fi

# Install the Watchdog package using Pip
pip3 install watchdog

# Create a systemd service unit file
cat <<EOF > /etc/systemd/system/printasyougo.service
[Unit]
Description=Print As You Go Server

[Service]
ExecStart=python3 /root/payg/payg-server.py
WorkingDirectory=/root/payg
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start the service
systemctl daemon-reload
systemctl enable printasyougo.service
systemctl start printasyougo.service
