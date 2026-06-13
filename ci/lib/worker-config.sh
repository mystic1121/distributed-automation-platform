#!/usr/bin/env bash
# ci/lib/worker-config.sh
# Shared configuration + state plumbing for the worker AMI rebake pipeline.

set -euo pipefail

REGION=ap-south-1
LT_NAME=kpi-automation-lt
ASG=kpi-automation-asg
SUBNET=subnet-08037fce56e279ce2
SG=sg-03d64a4d5f66c8019

# The commit being deployed. The Jenkinsfile exports TAG into the environment;

TAG="${TAG:-${1:-}}"
if [ -z "${TAG}" ]; then
  echo "FATAL: TAG (git sha) is not set"; exit 1
fi

# Cross-stage scratch space (lives in the Jenkins workspace, same node).
STATE_DIR="${STATE_DIR:-$PWD/.rebake-state}"
mkdir -p "$STATE_DIR"

IID_FILE="$STATE_DIR/builder-instance-id"
SHA_FILE="$STATE_DIR/baked-sha"
AMI_FILE="$STATE_DIR/ami-id"