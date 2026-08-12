#!/bin/bash
# Bakes the worker AMI. Installs Python 3.11 + the worker deps and the
# kpi-automation systemd unit (SQS consumer). 
set -euxo pipefail

sudo dnf update -y
sudo dnf install -y python3.11 python3.11-pip git

sudo mkdir -p /opt/kpi/kpi-automation-worker
sudo mv /tmp/prepost /opt/kpi/kpi-automation-worker/prepost
sudo chown -R ec2-user:ec2-user /opt/kpi

cd /opt/kpi/kpi-automation-worker/prepost
sudo python3.11 -m pip install -r requirements-automation.txt

# systemd unit. EnvironmentFile is written at boot by Terraform user-data.
sudo tee /etc/systemd/system/kpi-automation.service >/dev/null <<'UNIT'
[Unit]
Description=KPI Automation Worker (SQS consumer)
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/kpi/kpi-automation-worker/prepost
EnvironmentFile=/etc/kpi/automation.env
ExecStart=/usr/bin/python3.11 prepost_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
# Intentionally NOT enabled/started here (no env file yet at bake time).
