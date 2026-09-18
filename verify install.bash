#!/usr/bin/env bash

set -u

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
    exit 1
fi

# ----------------------------------------
# CHECK FACE TRACKER
# ----------------------------------------

if [ -f "$TRACKER_DIR/systems-monitor/face_tracker.py" ]; then
    echo "[PASS] face_tracker.py exists"
else
    echo "[FAIL] face_tracker.py missing"
fi

if [ -f "$TRACKER_DIR/systems-monitor/monitor_aim.py" ] && [ -f "$TRACKER_DIR/systems-monitor/as5600_test.py" ]; then
    echo "[PASS] monitor-aim and AS5600 programs exist"
else
    echo "[FAIL] monitor-aim or AS5600 program missing"
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

"$TRACKER_DIR/venv/bin/python" - <<EOF
try:
    import cv2
    print("[PASS] OpenCV installed")
    print("OpenCV Version:", cv2.__version__)
except:
    print("[FAIL] OpenCV not installed")
EOF

# ----------------------------------------
# CHECK MOTOR / I2C PYTHON DEPENDENCIES
# ----------------------------------------

"$TRACKER_DIR/venv/bin/python" - <<EOF
try:
    import gpiozero
    import smbus2
    print("[PASS] GPIO and I2C Python dependencies installed")
except Exception as error:
    print("[FAIL] GPIO or I2C dependency missing:", error)
EOF

# ----------------------------------------
# CHECK CAMERA
# ----------------------------------------

echo ""
echo "Checking camera devices..."

if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices
else
    echo "[FAIL] v4l2-ctl missing"
fi

# ----------------------------------------
# TEST CAMERA ACCESS
# ----------------------------------------

"$TRACKER_DIR/venv/bin/python" - <<EOF
import cv2

cap = cv2.VideoCapture(0)

if cap.isOpened():
    print("[PASS] Camera accessible")
else:
    print("[FAIL] Camera inaccessible")

cap.release()
EOF

# ----------------------------------------
# SAFE MONITOR-AIM DIAGNOSTIC
# ----------------------------------------

echo ""
echo "Running non-moving monitor-aim diagnostic..."
"$TRACKER_DIR/venv/bin/python" "$TRACKER_DIR/systems-monitor/monitor_aim.py" --test-only || true

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
