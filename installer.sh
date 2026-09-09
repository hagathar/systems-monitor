#!/usr/bin/env bash
set -euo pipefail

TRACKER_DIR="$HOME/tracker-file"
REPO_NAME="systems-monitor"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$TRACKER_DIR/$REPO_NAME"

echo "Pi Face Tracker installer"
echo "Installing to: $TRACKER_DIR"

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer supports Debian/Raspberry Pi OS systems only." >&2
    exit 1
fi

sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-opencv v4l-utils libopenblas-dev libjpeg-dev

mkdir -p "$PROJECT_DIR"
cp "$SOURCE_DIR/face_tracker.py" "$SOURCE_DIR/README.md" "$SOURCE_DIR/installer.sh" "$SOURCE_DIR/verify install.bash" "$PROJECT_DIR/"

if [ ! -d "$TRACKER_DIR/venv" ]; then
    python3 -m venv "$TRACKER_DIR/venv"
fi

"$TRACKER_DIR/venv/bin/python" -m pip install --upgrade pip
"$TRACKER_DIR/venv/bin/python" -m pip install numpy opencv-python

cat > "$TRACKER_DIR/start_tracker.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$TRACKER_DIR/venv/bin/python" "$PROJECT_DIR/face_tracker.py" "\$@"
EOF
chmod +x "$TRACKER_DIR/start_tracker.sh"

echo "Install complete. Run: $TRACKER_DIR/start_tracker.sh"
