#!/usr/bin/env bash
# Downloads all 100 synthetic companies into data/ (company-001 is already committed).
set -euo pipefail
cd "$(dirname "$0")/.."
URL="https://huggingface.co/datasets/CL251215/QuickBooks-Hackathon-2026/resolve/main/hackathon-100-participant.tar.gz"
curl -L -o data/hackathon-100.tar.gz "$URL"
tar -xzf data/hackathon-100.tar.gz -C data --strip-components=1
rm data/hackathon-100.tar.gz
echo "Done: $(ls -d data/company-* | wc -l) companies in data/"
