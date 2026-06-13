#!/usr/bin/env bash
# ci/worker/verify.sh
# STAGE 8: "Worker: Verify Commit SHA"

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/worker-config.sh
source "$HERE/lib/worker-config.sh"

BAKED_SHA="$(cat "$SHA_FILE")"


echo "Baked SHA on builder: '$BAKED_SHA'  (expected: '$TAG')"
if [ "$BAKED_SHA" != "$TAG" ]; then
  echo "ABORT: builder HEAD ($BAKED_SHA) does not match deploy tag ($TAG). The git update did not take — refusing to bake a stale AMI."
  exit 1
fi
echo "Verified: builder HEAD matches deploy tag $TAG."
