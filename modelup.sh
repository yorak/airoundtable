#!/bin/bash
docker run --gpus all -v /mnt/12TB/hugginfacecache -e HF_TOKEN=$HF_TOKEN -p 8000:8000 ghcr.io/mistralai/mistral-src/vllm:latest --host 0.0.0.0 --model mistralai/Mistral-7B-Instruct-v0.2 