#!/bin/bash

TRACKER_DIR="$HOME/tracker-file"

clear

echo "========================================="
echo " Pi 5 Face Tracker Install Verification"
echo "========================================="
echo ""

# ----------------------------------------
# CHECK MAIN DIRECTORY
# ----------------------------------------

if [ -d "$TRACKER_DIR" ]; then
    echo "[PASS] tracker-file directory exists"
else
    echo "[FAIL] tracker-file directory missing"
    exit 1
fi

# ----------------------------------------
# CHECK VENV
# ----------------------------------------

if [ -d "$TRACKER_DIR/venv" ]; then
    echo "[PASS] Python virtual environment exists"
else
    echo "[FAIL] venv missing"
fi

# ----------------------------------------
# CHECK FACE TRACKER
# ----------------------------------------

if [ -f "$TRACKER_DIR/face_tracker.py" ]; then
    echo "[PASS] face_tracker.py exists"
else
    echo "[FAIL] face_tracker.py missing"
fi

# ----------------------------------------
# CHECK START SCRIPT
# ----------------------------------------

if [ -f "$TRACKER_DIR/start_tracker.sh" ]; then
    echo "[PASS] start_tracker.sh exists"
else
    echo "[FAIL] start_tracker.sh missing"
fi

# ----------------------------------------
# CHECK GITHUB REPO
# ----------------------------------------

if [ -d "$TRACKER_DIR/systems-monitor" ]; then
    echo "[PASS] systems-monitor repo exists"
else
    echo "[FAIL] systems-monitor repo missing"
fi

# ----------------------------------------
# CHECK PYTHON
# ----------------------------------------

if command -v python3 >/dev/null 2>&1; then
    echo "[PASS] Python3 installed"
    python3 --version
else
    echo "[FAIL] Python3 missing"
fi

# ----------------------------------------
# CHECK OPENCV
# ----------------------------------------

source "$TRACKER_DIR/venv/bin/activate"

python - <<EOF
try:
    import cv2
    print("[PASS] OpenCV installed")
    print("OpenCV Version:", cv2.__version__)
except:
    print("[FAIL] OpenCV not installed")
EOF

# ----------------------------------------
# CHECK CAMERA
# ----------------------------------------

echo ""
echo "Checking camera devices..."

v4l2-ctl --list-devices

# ----------------------------------------
# TEST CAMERA ACCESS
# ----------------------------------------

python - <<EOF
import cv2

cap = cv2.VideoCapture(0)

if cap.isOpened():
    print("[PASS] Camera accessible")
else:
    print("[FAIL] Camera inaccessible")

cap.release()
EOF

# ----------------------------------------
# COMPLETE
# ----------------------------------------

echo ""
echo "========================================="
echo " Verification Complete"
echo "========================================="
echo ""

echo "Project Location:"
echo "$TRACKER_DIR"

echo ""
echo "To run tracker:"
echo "~/tracker-file/start_tracker.sh"