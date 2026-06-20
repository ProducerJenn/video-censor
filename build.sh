#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$DIR/../censor_env/bin/app.py" "$DIR/"
cp "$DIR/../censor_env/bin/app2.py" "$DIR/"
cp "$DIR/../censor_env/bin/app3.py" "$DIR/"
cp "$DIR/../badwords.txt" "$DIR/" 2>/dev/null || true
echo "Copied app scripts. Now run: docker compose build"
