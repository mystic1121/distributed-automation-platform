#!/usr/bin/env bash
# ci/backend/build-image.sh
# STAGE 2: "Backend: Build Docker Image"
#
# Authenticate to ECR and build the backend image. 

set -euo pipefail

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR
docker build -t $ECR/kpi-backend:$TAG kpi-automation-backend
