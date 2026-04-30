#!/usr/bin/env bash
# One-command demo. Run this on the demo-day laptop with no internet.
#
#   bash demo.sh
#
# It will:
#   1. install dependencies (best-effort, into the active Python env)
#   2. generate synthetic pcaps for Zoom / Discord / YouTube / Spotify / Web
#   3. analyze the combined "mixed.pcap" and print the report to the terminal
#   4. write four chart PNGs under reports/mixed/

set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "==> installing dependencies (no-ops if already satisfied)"
"$PY" -m pip install --quiet -r requirements.txt

echo "==> running demo pipeline"
"$PY" -m traffic_analyzer demo \
    --pcap-dir pcaps \
    --report-dir reports/mixed

echo
echo "==> done."
echo "    pcaps    -> $(pwd)/pcaps/"
echo "    charts   -> $(pwd)/reports/mixed/"
echo
echo "Tip: open reports/mixed/04_flow_fingerprints.png during the demo --"
echo "     it visually separates Zoom/Discord/YouTube/Spotify/Web in one shot."
