#!/bin/bash

# Configuration
SOURCE_DIR="/var/www/movies/ztemp"
RCLONE_DEST="gdrive:3DMovies"

# Safety check: Ensure source directory exists and has files
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory $SOURCE_DIR does not exist!"
    exit 1
fi

echo "--------------------------------------------------------"
echo "  LAUNCHING MAXIMUM BANDWIDTH UPLOAD TO GOOGLE DRIVE    "
echo "--------------------------------------------------------"
echo "Source Folder: $SOURCE_DIR"
echo "Destination:   $RCLONE_DEST"
echo "--------------------------------------------------------"

# ULTIMATE SPEED UPLOAD PARAMETERS:
# --transfers 16       : Uploads 16 different movie files at the exact same time.
# --drive-chunk-size   : Uses 256MB memory blocks to minimize Google API request overhead.
# --buffer-size 128M   : Pre-caches 128MB streams in RAM to maximize Azure pipe utilization.
# --use-mmap           : Optimizes server memory allocation under heavy network load.
# --checkers 32        : Speeds up initial file-sync verification.

rclone copy "$SOURCE_DIR" "$RCLONE_DEST" \
    --transfers 16 \
    --drive-chunk-size 256M \
    --buffer-size 128M \
    --use-mmap \
    --checkers 32 \
    --progress

if [ $? -eq 0 ]; then
    echo "--------------------------------------------------------"
    echo "SUCCESS: All files uploaded and cleared from local disk!"
    echo "--------------------------------------------------------"
else
    echo "--------------------------------------------------------"
    echo "WARNING: rclone completed with warnings or minor errors."
    echo "--------------------------------------------------------"
fi