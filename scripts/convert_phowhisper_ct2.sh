#!/bin/bash
# PhoWhisper goc la checkpoint PyTorch -> phai convert 1 lan sang CTranslate2
# moi dung duoc voi faster-whisper. Chay 1 lan tren VPS.
set -e
pip install -q ctranslate2 transformers
ct2-transformers-converter --model vinai/PhoWhisper-large \
  --output_dir models/phowhisper-large-ct2 \
  --quantization float16
echo "Xong. Dat PHOWHISPER_CT2_DIR=models/phowhisper-large-ct2 trong .env"
