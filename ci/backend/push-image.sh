#!/usr/bin/env bash
# ci/backend/push-image.sh
# STAGE 3: "Backend: Push Image to ECR"
#
# Push the freshly built backend image to ECR 

set -euo pipefail

docker push $ECR/kpi-backend:$TAG
