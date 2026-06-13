#!/usr/bin/env bash
# ci/worker/cleanup.sh
# Runs in the Jenkins post{ always { ... } } block.
#

set -euo pipefail

REGION=ap-south-1
STATE_DIR="${STATE_DIR:-$PWD/.rebake-state}"
IID_FILE="$STATE_DIR/builder-instance-id"

if [ -s "$IID_FILE" ]; then
  IID="$(cat "$IID_FILE")"
  echo "Cleanup: terminating temporary builder $IID"
  aws ec2 terminate-instances --region $REGION --instance-ids "$IID" >/dev/null 2>&1 || true
else
  echo "Cleanup: no builder instance recorded — nothing to terminate."
fi
