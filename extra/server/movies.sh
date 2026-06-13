#!/bin/bash

# Configuration
JSON_FILE="$(pwd)/data.json"
INPUT_TXT="$(pwd)/aria_input.txt"
WORK_DIR="/root/Data/ztemp"

if [ ! -f "$JSON_FILE" ]; then
    echo "Error: '$JSON_FILE' not found!"
    exit 1
fi

mkdir -p "$WORK_DIR"

echo "Converting data.json to fast-input list..."
# This cleanly formats the JSON titles and links into aria2c native format
python3 -c "
import json, os
with open('$JSON_FILE') as f:
    data = json.load(f)
with open('$INPUT_TXT', 'w') as out:
    for item in data:
        if item.get('stream_url') and item.get('title'):
            out.write(f\"{item['stream_url']}\n\")
            out.write(f\"  out={item['title']}.mp4\n\")
"

echo "Switching to working directory: $WORK_DIR"
cd "$WORK_DIR" || exit 1

echo "--------------------------------------------------"
echo "BLASTING DOWNLOADS IN MULTI-FILE PARALLEL MODE"
echo "--------------------------------------------------"

# ULTIMATE PARALLEL PARAMETERS:
# -j 10  : Download 10 different movie files at the exact same time!
# -x 16  : Open up to 16 connections per file.
# -s 16  : Split each file into 16 pieces.
# --summary-interval=5 : Show clean speed updates every 5 seconds.
aria2c -i "$INPUT_TXT" \
       -j 10 -x 16 -s 16 \
       -k 1M \
       --auto-file-renaming=false \
       --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
       --summary-interval=5 \
       --download-result=hide

# Clean up input file after starting
rm -f "$INPUT_TXT"

echo "--------------------------------------------------"
echo "All done! Check your /root/Data/ztemp folder."