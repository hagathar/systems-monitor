# Pi Face Tracker

A Raspberry Pi / Linux webcam face tracker. It shows the selected face, the
recent path it travelled, its current position relative to the screen centre,
and an arrow for its current heading.

## Preview annotations

- **Green line and dots:** where the selected face has been during the recent tracking window.
- **Red dot:** current face centre.
- **Yellow arrow:** smoothed direction of travel, based on the recent path.
- **Position:** normalized `PAN` and `TILT` values from `-1` to `+1`.
- **Heading:** horizontal and vertical movement in pixels per frame.

Press **Esc** in the preview window to stop.

## Install on Raspberry Pi OS

Open a terminal on the Pi (or connect with SSH), then clone the repository and
run the installer:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/hagathar/systems-monitor.git ~/systems-monitor
cd ~/systems-monitor
chmod +x installer.sh
./installer.sh
```

The installer keeps existing files in `~/tracker-file`, copies this project to
`~/tracker-file/systems-monitor`, and creates `~/tracker-file/start_tracker.sh`.
It requires a Debian/Raspberry Pi OS system because it uses `apt-get`.

### Manual installation

If you prefer not to use the installer, run these commands after cloning the
repository above:

```bash
cd ~/systems-monitor
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-opencv v4l-utils libopenblas-dev libjpeg-dev
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install numpy opencv-python
python face_tracker.py
```

The tracker needs a webcam exposed as `/dev/video0` and opens a graphical
preview window. Run it from the Pi desktop, or use an SSH session configured
for graphical forwarding; a plain headless SSH session cannot display the
preview.

## Run

```bash
~/tracker-file/start_tracker.sh
```

Options can be passed through to the tracker:

```bash
# Use camera 1, mirror the preview, and keep the most recent 90 points
~/tracker-file/start_tracker.sh --camera 1 --mirror --history 90
```

## Verify an installation

```bash
chmod +x "verify install.bash"
./"verify install.bash"
```
