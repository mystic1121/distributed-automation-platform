#!/usr/bin/env bash
# ci/worker/refresh-asg.sh
# STAGE 11: "Worker: Refresh ASG"
#
# Roll the worker fleet onto the new AMI via an ASG instance refresh.
#
# Logic preserved verbatim from rebake-worker-ami.sh step (7).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

AMI="$(cat "$AMI_FILE")"

# 7) roll the worker fleet onto the new AMI
aws autoscaling start-instance-refresh --region $REGION \
  --auto-scaling-group-name "$ASG" \
  --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":120}'
echo "Worker rebake complete: $AMI rolling out."
