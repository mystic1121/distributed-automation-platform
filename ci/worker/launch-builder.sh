#!/usr/bin/env bash
# ci/worker/launch-builder.sh
# STAGE: "Worker: Launch Builder"
#
# Launches a private builder instance from the current base AMI and waits until
# the SSM agent is reachable. The builder's instance-id is written to STATE_DIR
# so later stages (provision/bake) and the cleanup stage can find it.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

BASE_AMI=$(aws ssm get-parameter --name /kpi/automation/ami-id --query Parameter.Value --output text --region $REGION)
echo "Building from base AMI $BASE_AMI"

# 1) launch a private builder with the automation role (so SSM can reach it)
IID=$(aws ec2 run-instances --region $REGION \
  --image-id "$BASE_AMI" --instance-type t3.medium \
  --subnet-id "$SUBNET" --no-associate-public-ip-address \
  --security-group-ids "$SG" \
  --iam-instance-profile Name=ec2-automation-role \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=kpi-automation-builder}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "Builder: $IID"
# Persist the instance-id immediately so the cleanup stage can always terminate

printf '%s' "$IID" > "$IID_FILE"
aws ec2 wait instance-running --region $REGION --instance-ids "$IID"

# 2) wait for the SSM agent to come online
until [ "$(aws ssm describe-instance-information --region $REGION \
        --filters Key=InstanceIds,Values=$IID \
        --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null)" = "Online" ]; do
  echo "waiting for SSM..."; sleep 10
done
echo "Builder $IID is online and ready to provision."