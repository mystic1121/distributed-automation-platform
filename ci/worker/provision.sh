#!/usr/bin/env bash
# ci/worker/provision.sh
# STAGE: "Worker: Fresh Clone Repository"
#
# Runs the provisioning command on the builder over SSM: FRESH-CLONE the repo,
# fix dubious-ownership, run integrity (fsck) + non-empty file checks, install
# deps, and print BAKED_SHA. The resolved short SHA is parsed out and saved to
# STATE_DIR for the next stage ("Verify Commit SHA") to gate on.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

IID="$(cat "$IID_FILE")"


CMD=$(aws ssm send-command --region $REGION --instance-ids "$IID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "set -euo pipefail",
    "REPO=https://github.com/mystic1153/aws-kpi-automation-platform.git",
    "sudo rm -rf /opt/kpi",
    "sudo git clone $REPO /opt/kpi",
    "sudo chown -R ec2-user:ec2-user /opt/kpi",
    "git config --system --add safe.directory /opt/kpi",
    "cd /opt/kpi && sudo -u ec2-user git reset --hard origin/main",
    "sudo -u ec2-user git -C /opt/kpi fsck --connectivity-only",
    "test -s /opt/kpi/kpi-automation-worker/prepost/rcp_prepost_runner.py",
    "test -s /opt/kpi/kpi-automation-worker/prepost/utilities.py",
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

# Extract BAKED_SHA here (where OUT is in scope) and hand it to the verify stage.
BAKED_SHA=$(echo "$OUT" | sed -n 's/^BAKED_SHA=//p' | tail -n1)
printf '%s' "$BAKED_SHA" > "$SHA_FILE"
echo "Recorded baked SHA on builder: '$BAKED_SHA'"