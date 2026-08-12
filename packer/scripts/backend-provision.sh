#!/bin/bash
# Bakes the backend AMI. Installs Docker + Nginx, builds the kpi-backend image,
# drops the Nginx reverse-proxy config. 
set -euxo pipefail

sudo dnf update -y
sudo dnf install -y git nginx docker
sudo systemctl enable docker
sudo systemctl start docker

sudo mkdir -p /opt/kpi
sudo mv /tmp/kpi-automation-backend /opt/kpi/kpi-automation-backend
sudo chown -R ec2-user:ec2-user /opt/kpi

# Build the application image and bake it into the AMI.
cd /opt/kpi/kpi-automation-backend
sudo docker build -t kpi-backend:latest .


sudo tee /etc/nginx/nginx.conf >/dev/null <<'BASE'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;
    include /etc/nginx/conf.d/*.conf;
}
BASE

# Nginx: port 80 -> Gunicorn container on 127.0.0.1:5000
sudo tee /etc/nginx/conf.d/kpi.conf >/dev/null <<'NGINX'
server {
    listen 80 default_server;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
        client_max_body_size 50M;
    }
}
NGINX

sudo systemctl enable nginx
sudo nginx -t
