#!/usr/bin/env bash
# ci/backend/update-image-tag.sh
# STAGE 4: "Backend: Update Image Tag"
#
# Publish the new image tag to SSM so the backend fleet picks it up on refresh.

set -euo pipefail

aws ssm put-parameter --name /kpi/backend/image-tag --type String --overwrite --value $TAG --region $AWS_REGION
