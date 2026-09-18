#!/usr/bin/env bash
set -euo pipefail

TRACKER_DIR="$HOME/tracker-file"
REPO_NAME="systems-monitor"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$TRACKER_DIR/$REPO_NAME"

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This updater supports Debian/Raspberry Pi OS systems only." >&2
    exit 1
fi

echo "Updating Pi Face Tracker, AS5600 test, and monitor-aim controller dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-opencv python3-lgpio v4l-utils i2c-tools libopenblas-dev libjpeg-dev

mkdir -p "$PROJECT_DIR"
if [ "$SOURCE_DIR" != "$PROJECT_DIR" ]; then
    cp "$SOURCE_DIR/README.md" "$SOURCE_DIR/requirements.txt" "$SOURCE_DIR/face_tracker.py" "$SOURCE_DIR/as5600_test.py" "$SOURCE_DIR/monitor_aim.py" "$SOURCE_DIR/installer.sh" "$SOURCE_DIR/update.sh" "$SOURCE_DIR/verify install.bash" "$PROJECT_DIR/"
fi

if [ ! -d "$TRACKER_DIR/venv" ]; then
    python3 -m venv "$TRACKER_DIR/venv"
fi

"$TRACKER_DIR/venv/bin/python" -m pip install --upgrade pip
"$TRACKER_DIR/venv/bin/python" -m pip install --upgrade --force-reinstall --no-cache-dir -r "$PROJECT_DIR/requirements.txt"

cat > "$TRACKER_DIR/start_tracker.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$TRACKER_DIR/venv/bin/python" "$PROJECT_DIR/face_tracker.py" "\$@"
EOF

cat > "$TRACKER_DIR/test_as5600.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$TRACKER_DIR/venv/bin/python" "$PROJECT_DIR/as5600_test.py" "\$@"
EOF

cat > "$TRACKER_DIR/aim_monitor.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$TRACKER_DIR/venv/bin/python" "$PROJECT_DIR/monitor_aim.py" "\$@"
EOF

chmod +x "$TRACKER_DIR/start_tracker.sh" "$TRACKER_DIR/test_as5600.sh" "$TRACKER_DIR/aim_monitor.sh"
echo "Update complete."
echo "Face tracker: $TRACKER_DIR/start_tracker.sh"
echo "AS5600 test:  $TRACKER_DIR/test_as5600.sh"
echo "Monitor aim:   $TRACKER_DIR/aim_monitor.sh --test-only"
