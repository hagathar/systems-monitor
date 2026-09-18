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

## AS5600 angle-sensor test

The test supports the three AS5600 sensors connected to a **PCA9548A** I2C multiplexer. (The part written as “PCA95448A” in the wiring list appears to be the PCA9548A.) Its wiring assumes the mux is at `0x70` because A0 and A1 are grounded, and that one AS5600 is connected to each of mux channels 0, 1, and 2. All AS5600 sensors use their default address, `0x36`; placing each one on a separate mux channel is therefore required.

Enable I2C first on the Pi:

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable, then reboot if prompted
```

Run the updater after pulling this repository version. It installs `i2c-tools` and the Python `smbus2` dependency, copies the test into the installed project, and creates its launcher:

```bash
./update.sh
~/tracker-file/test_as5600.sh
```

By default, the test reads channels 0, 1, and 2 continuously and prints every sensor's position in degrees and raw 12-bit value every two seconds. Press Ctrl-C to stop. Use `--interval` to change the interval or `--count` for a finite test. To test different mux ports, provide their comma-separated channel numbers:

```bash
~/tracker-file/test_as5600.sh --channels 2,4,6 --count 10 --interval 0.25
```

Each result also reports whether the magnet field is valid, too weak, too strong, or absent.

## Monitor face-aim controller

`monitor_aim.py` runs a startup diagnostic for the camera, all configured AS5600
channels, the L298N actuator-driver GPIO setup, and the TB6612 stepper-driver
GPIO setup. It then opens a face preview with a green crosshair for the face
target and a cyan crosshair for the **estimated** monitor aim. The terminal
reports the face location, estimated aim, and encoder values every two seconds.
Press Esc, Q, or X to stop; all motor outputs are disabled in every exit path.

```bash
./update.sh
~/tracker-file/aim_monitor.sh --test-only
~/tracker-file/aim_monitor.sh --mirror
```

The controller is dry-run by default: it never opens motor GPIOs or energises a
motor. This lets you verify the camera and all three encoders first.

### Local preview on Raspberry Pi OS Lite

Pi OS Lite has no graphical desktop, so the OpenCV crosshair window cannot run
from its normal console alone. To use the HDMI-connected Pi monitor locally,
install the required Wayland desktop packages without remote-access extras,
then reboot:

```bash
cd ~/systems-monitor
git pull origin main
./update.sh --lite-preview
sudo reboot
```

After rebooting into the local desktop, open a terminal on the Pi and run:

```bash
~/tracker-file/aim_monitor.sh --mirror
```

The program prints a clear setup message rather than attempting to open a
preview from a non-graphical console. `--test-only` and the AS5600 terminal
test remain usable without a desktop.

### Revised motor wiring

The L298N now drives the two Y-axis linear actuators synchronously, one on each
H-bridge channel. With its
ENA/ENB jumpers installed, it uses short **60 ms full-power pulses**; it cannot
use software PWM speed control until those jumpers are removed and ENA/ENB are
wired to PWM-capable GPIO pins.

| Driver | Function | GPIO pins |
| --- | --- | --- |
| L298N | Y actuator A | IN1 GPIO 24, IN2 GPIO 22 |
| L298N | Y actuator B | IN3 GPIO 23, IN4 GPIO 25 |
| TB6612FNG | X stepper coil A | PWMA GPIO 20, AIN1 GPIO 5, AIN2 GPIO 17 |
| TB6612FNG | X stepper coil B | PWMB GPIO 18, BIN1 GPIO 27, BIN2 GPIO 16 |
| TB6612FNG | Stepper enable | STBY GPIO 14 |

This map has no GPIO conflicts. The TB6612's two H-bridges now drive the two
coils of the X **four-wire bipolar stepper**, while the L298N handles only the
Y actuators.

After testing the physical actuator end limits and calibrating how many full
steps move the monitor across one camera-screen width, allow motion with:

```bash
~/tracker-file/aim_monitor.sh --mirror --enable-motion --confirm-y-limits \
  --steps-per-screen 3200
```

Use `--invert-y` or `--invert-x` if an axis initially moves in the wrong
direction. The program refuses movement without both `--enable-motion` and
`--confirm-y-limits`; it de-energises the TB6612 between step pulses. The
monitor-aim crosshair remains explicitly labelled *estimated* until encoder and
mechanical calibration are added.

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
pip install -r requirements.txt
python face_tracker.py
```

The tracker needs a webcam exposed as `/dev/video0` and opens a graphical
preview window. Run it from the Pi desktop, or use an SSH session configured
for graphical forwarding; a plain headless SSH session cannot display the
preview.

### NumPy/OpenCV compatibility repair

If importing `cv2` reports that a module compiled against NumPy 1.x cannot run
with NumPy 2.x, install the version pair pinned by this project. From the
cloned repository, run:

```bash
~/tracker-file/venv/bin/python -m pip install --upgrade --force-reinstall --no-cache-dir -r requirements.txt
```

Then start the tracker again. The installer runs the same command, so rerunning
`./installer.sh` also repairs an existing installation.

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
