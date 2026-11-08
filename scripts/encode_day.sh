#!/bin/bash
# Encode one day's frame dump into a 60fps timelapse (10x real time), then delete frames.
set -e
D="$(cd "$(dirname "$0")/.." && pwd)/media"
mkdir -p "$D/video"
day=$1
nice -n 15 ffmpeg -y -loglevel error -framerate 60 -pattern_type glob -i "$D/frames/$day/f*.png" \
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$D/video/$day.mp4"
[ -s "$D/video/$day.mp4" ] && rm -rf "$D/frames/$day"
ls -la "$D/video/$day.mp4"
