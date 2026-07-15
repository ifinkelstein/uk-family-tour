#!/usr/bin/env bash
# Prepare ALL offline assets in one go: images from Wikipedia + natural
# voices via Kokoro-82M, then verify completeness. Run on a Mac (or any
# machine with internet); afterwards the app itself never touches the network.
#
#   cd scripts && ./prepare_assets.sh
#
# Options via env:
#   KID_VOICE=bf_emma ADULT_VOICE=bm_george SPEED=1.0 ./prepare_assets.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 System dependencies (Homebrew) =="
if ! command -v brew >/dev/null; then
  echo "Homebrew required: https://brew.sh"; exit 1
fi
brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng
brew list ffmpeg   >/dev/null 2>&1 || brew install ffmpeg

echo "== 2/4 Python environment =="
if [ ! -d venv ]; then python3 -m venv venv; fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q kokoro soundfile

echo "== 3/4 Downloading images (Wikipedia lead images) =="
python3 fetch_images.py

echo "== 4/4 Generating voices (Kokoro-82M — first run downloads ~330MB model) =="
python3 generate_audio.py \
  --manifest ../tour/manifest.json \
  --out ../tour/audio \
  --kid-voice "${KID_VOICE:-bf_emma}" \
  --adult-voice "${ADULT_VOICE:-bm_george}" \
  --speed "${SPEED:-1.0}"

echo "== Verifying =="
python3 verify_assets.py

echo
echo "Assets ready. Serve the web app from the project root (see AGENT.md or README.md)."
