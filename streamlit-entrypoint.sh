#!/bin/bash
set -e
APP="${1:-app3.py}"
case "$APP" in
  app.py|app2.py|app3.py) ;;
  *) echo "Usage: docker run ... [app.py|app2.py|app3.py]" && exit 1 ;;
esac
exec streamlit run "$APP" --server.port=8501 --server.address=0.0.0.0
