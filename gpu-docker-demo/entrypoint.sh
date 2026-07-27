#!/bin/bash
set -e

case "$1" in
  train) exec python3 train.py ;;
  infer) exec python3 infer.py ;;
  *) echo "Usage: docker run --gpus all gpu-demo [train|infer]"; exit 1 ;;
esac
