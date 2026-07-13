#!/bin/bash
set -e

cd "$(dirname "$0")/.."

IMAGE="nas-brain"

echo "=== Building Docker image ==="
docker build -t $IMAGE -f deploy/Dockerfile .

echo ""
echo "=== Build complete ==="
echo "Run with: deploy/run_docker.sh"
