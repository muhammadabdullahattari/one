#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Starting Pre-Deployment Database Migration Sequence"
echo "=========================================================="

python3 scripts/deploy_migrate.py "$@"

echo "=========================================================="
echo " Pre-Deployment Migration Sequence Finished Successfully"
echo "=========================================================="
