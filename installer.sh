#!/bin/bash

set -e

TRACKER_DIR="$HOME/tracker-file"
REPO_URL="https://github.com/hagathar/systems-monitor.git"
REPO_NAME="systems-monitor"

clear

echo "========================================="
echo " Pi 5 Face Tracker Auto Installer"
echo "========================================="
echo ""

# --------------------------------------------------
# CHECK FOR EXISTING INSTALL
# --------------------------------------------------

if [ -d "$TRACKER_DIR" ]; then
    echo "Existing tracker-file installation found"
    echo "Removing old installation..."

    rm -rf "$TRACKER_DIR"

    echo "Old installation removed"
    echo ""
fi

# --------------------------------------------------
# SYSTEM UPDATE
# --------------------------------------------------

echo "Updating system..."

sudo apt update
sudo apt full-upgrade -y

# --------------------------------------------------
# INSTALL DEPENDENCIES
# --------------------------------------------------

echo "Installing dependencies..."

sudo apt install -y \
python3-pip \
python3-venv \
python3-opencv \
v4l-utils \
git \
libopenblas-dev \
libjpeg-dev

# --------------------------------------------------
# CREATE PROJECT FOLDER
# --------------------------------------------------

echo "Creating project directory..."

mkdir -p "$TRACKER_DIR"
cd "$TRACKER_DIR"

# --------------------------------------------------
# CREATE VIRTUAL ENVIRONMENT
# --------------------------------------------------

echo "Creating Python virtual environment..."

python3 -m venv venv

source venv/bin/activate

# --------------------------------------------------
# UPDATE PIP
# --------------------------------------------------

echo "Updating pip..."

pip install --upgrade pip

# --------------------------------------------------
# INSTALL PYTHON PACKAGES
# --------------------------------------------------

echo "Installing Python packages..."

pip install numpy opencv-python

# --------------------------------------------------
# CREATE START SCRIPT
# --------------------------------------------------

echo "Creating launcher script..."

cat > start_tracker.sh << 'EOF'
#!/bin/bash

cd ~/tracker-file

source venv/bin/activate

python face_tracker.py
EOF

chmod +x start_tracker.sh

# --------------------------------------------------
# COMPLETE
# --------------------------------------------------

echo ""
echo "========================================="
echo " INSTALL COMPLETE"
echo "========================================="
echo ""
echo "Tracker installed to:"
echo "$TRACKER_DIR"
echo ""
echo "GitHub repo installed to:"
echo "$TRACKER_DIR/$REPO_NAME"
echo ""
echo "Run tracker with:"
echo "~/tracker-file/start_tracker.sh"
echo ""