#!/usr/bin/env bash
# ci/backend/refresh-asg.sh
# STAGE 5: "Backend: Refresh ASG"
#
# Roll the backend fleet so instances pull the new image tag.

set -euo pipefail

aws autoscaling start-instance-refresh --auto-scaling-group-name $BACKEND_ASG \
  --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":120}' --region $AWS_REGION
