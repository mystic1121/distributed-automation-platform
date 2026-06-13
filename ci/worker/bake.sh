#!/usr/bin/env bash
# ci/worker/bake.sh
# STAGE 9: "Worker: Bake AMI"
#
# Flush + STOP the builder so the snapshot is consistent, then create-image and
# wait until it is available. 

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

IID="$(cat "$IID_FILE")"


aws ssm send-command --region $REGION --instance-ids "$IID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["sync","sleep 3","sync"]' \
  --query 'Command.CommandId' --output text >/dev/null || true
aws ec2 stop-instances --region $REGION --instance-ids "$IID" >/dev/null
aws ec2 wait instance-stopped --region $REGION --instance-ids "$IID"

# 4) bake the new AMI (instance is now stopped → snapshot is consistent;

AMI=$(aws ec2 create-image --region $REGION --instance-id "$IID" \
  --name "kpi-automation-ami-$TAG" --no-reboot --query ImageId --output text)
echo "New AMI: $AMI"
printf '%s' "$AMI" > "$AMI_FILE"
aws ec2 wait image-available --region $REGION --image-ids "$AMI"
