#!/usr/bin/env bash
# ci/rebake-worker-ami.sh  <git-sha>
set -euo pipefail
TAG="$1"
REGION=ap-south-1
LT_NAME=kpi-automation-lt
ASG=kpi-automation-asg
SUBNET=subnet-08037fce56e279ce2
SG=sg-03d64a4d5f66c8019

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
trap 'aws ec2 terminate-instances --region $REGION --instance-ids "$IID" >/dev/null 2>&1 || true' EXIT
aws ec2 wait instance-running --region $REGION --instance-ids "$IID"

# 2) wait for the SSM agent to come online
until [ "$(aws ssm describe-instance-information --region $REGION \
        --filters Key=InstanceIds,Values=$IID \
        --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null)" = "Online" ]; do
  echo "waiting for SSM..."; sleep 10
done

# 3) pull the new code onto the builder + refresh deps
#      
#   - print the resolved short SHA as the LAST line of stdout so the
#     Jenkins side can assert it matches $TAG before baking.
CMD=$(aws ssm send-command --region $REGION --instance-ids "$IID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "set -euo pipefail",
    "git config --system --add safe.directory /opt/kpi",
    "cd /opt/kpi",
    "sudo -u ec2-user git fetch --all --prune",
    "sudo -u ec2-user git reset --hard origin/main",
    "cd /opt/kpi/kpi-automation-worker/prepost && pip3.11 install -q -r requirements-automation.txt",
    "cd /opt/kpi && echo BAKED_SHA=$(sudo -u ec2-user git rev-parse --short HEAD)"]' \
  --query 'Command.CommandId' --output text)
aws ssm wait command-executed --region $REGION --command-id "$CMD" --instance-id "$IID" || true
STATUS=$(aws ssm get-command-invocation --region $REGION --command-id "$CMD" --instance-id "$IID" --query Status --output text)
OUT=$(aws ssm get-command-invocation --region $REGION --command-id "$CMD" --instance-id "$IID" --query StandardOutputContent --output text)
ERR=$(aws ssm get-command-invocation --region $REGION --command-id "$CMD" --instance-id "$IID" --query StandardErrorContent --output text)
echo "Provision status: $STATUS"
echo "----- builder stdout -----"; echo "$OUT"
[ "$STATUS" = "Success" ] || { echo "Provisioning failed"; echo "----- builder stderr -----"; echo "$ERR"; exit 1; }

# 3b) HARD GATE: the code baked into the AMI must match the commit we are deploying.

BAKED_SHA=$(echo "$OUT" | sed -n 's/^BAKED_SHA=//p' | tail -n1)
echo "Baked SHA on builder: '$BAKED_SHA'  (expected: '$TAG')"
if [ "$BAKED_SHA" != "$TAG" ]; then
  echo "ABORT: builder HEAD ($BAKED_SHA) does not match deploy tag ($TAG). The git update did not take — refusing to bake a stale AMI."
  exit 1
fi

# 4) bake the new AMI
AMI=$(aws ec2 create-image --region $REGION --instance-id "$IID" \
  --name "kpi-automation-ami-$TAG" --no-reboot --query ImageId --output text)
echo "New AMI: $AMI"
aws ec2 wait image-available --region $REGION --image-ids "$AMI"

# 5) point the launch template at the new AMI + make it default
aws ec2 create-launch-template-version --region $REGION \
  --launch-template-name "$LT_NAME" --source-version '$Latest' \
  --launch-template-data "{\"ImageId\":\"$AMI\"}"
aws ec2 modify-launch-template --region $REGION \
  --launch-template-name "$LT_NAME" --default-version '$Latest'

# 6) remember this AMI as the base for next time
aws ssm put-parameter --region $REGION --name /kpi/automation/ami-id \
  --type String --overwrite --value "$AMI"

# 7) roll the worker fleet onto the new AMI
aws autoscaling start-instance-refresh --region $REGION \
  --auto-scaling-group-name "$ASG" \
  --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":120}'
echo "Worker rebake complete: $AMI rolling out."