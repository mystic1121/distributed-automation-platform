#!/usr/bin/env bash
# ci/worker/update-launch-template.sh
# STAGE 10: "Worker: Update Launch Template"
#
# Point the launch template at the freshly baked AMI, make that version the
# default, and remember the AMI in SSM as the base for the next rebake.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

AMI="$(cat "$AMI_FILE")"

# 5) point the launch template at the new AMI + make it default
aws ec2 create-launch-template-version --region $REGION \
  --launch-template-name "$LT_NAME" --source-version '$Latest' \
  --launch-template-data "{\"ImageId\":\"$AMI\"}"
aws ec2 modify-launch-template --region $REGION \
  --launch-template-name "$LT_NAME" --default-version '$Latest'

# 6) remember this AMI as the base for next time
aws ssm put-parameter --region $REGION --name /kpi/automation/ami-id \
  --type String --overwrite --value "$AMI"
