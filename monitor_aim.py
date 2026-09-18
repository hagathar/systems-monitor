#!/usr/bin/env python3
"""Safely aim a monitor at a detected face using the supplied Raspberry Pi wiring."""

import argparse
import sys
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from as5600_test import (
    AS5600_DEFAULT_ADDRESS,
    PCA9548A_DEFAULT_ADDRESS,
    read_sensor,
    select_channel,
)


# TB6612FNG wiring from the supplied pin map. Motor A is reserved for the Y actuator.
TB6612_PINS = {
    "pwma": 20,
    "ain2": 27,
    "ain1": 17,
    "stby": 14,
    "bin1": 22,
    "bin2": 16,
    "pwmb": 18,
}
MAX_DUTY = 0.35
MAX_PULSE_SECONDS = 0.12
CONTROL_PERIOD_SECONDS = 0.18
DEAD_ZONE_PIXELS = 24


def parse_channels(value):
    try:
        channels = [int(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Channels must be comma-separated integers") from error
    if not channels or any(channel not in range(8) for channel in channels):
        raise argparse.ArgumentTypeError("Each PCA9548A channel must be between 0 and 7")
    return channels


def draw_crosshair(cv2, frame, point, color, label):
    x, y = map(int, point)
    cv2.line(frame, (x - 16, y), (x + 16, y), color, 2)
    cv2.line(frame, (x, y - 16), (x, y + 16), color, 2)
    cv2.circle(frame, (x, y), 5, color, 2)
    cv2.putText(frame, label, (x + 20, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def duty_for_error(error):
    return clamp(0.12 + abs(error) / 900, 0.12, MAX_DUTY)


class Tb6612Channel:
    """One TB6612FNG H-bridge channel, always created in its stopped state."""

    def __init__(self, in1, in2, pwm):
        self.in1 = in1
        self.in2 = in2
        self.pwm = pwm
        self.stop()

    def drive(self, direction, duty):
        self.in1.value = direction > 0
        self.in2.value = direction < 0
        self.pwm.value = clamp(duty, 0, MAX_DUTY)

    def stop(self):
        self.pwm.value = 0
        self.in1.off()
        self.in2.off()

    def close(self):
        self.stop()
        self.in1.close()
        self.in2.close()
        self.pwm.close()


class Tb6612Driver:
    """TB6612FNG driver. Channel A is Y; Channel B is only for a two-wire DC rotator."""

    def __init__(self):
        from gpiozero import OutputDevice, PWMOutputDevice

        self.stby = OutputDevice(TB6612_PINS["stby"], initial_value=False)
        self.y = Tb6612Channel(
            OutputDevice(TB6612_PINS["ain1"], initial_value=False),
            OutputDevice(TB6612_PINS["ain2"], initial_value=False),
            PWMOutputDevice(TB6612_PINS["pwma"], frequency=1_000, initial_value=0),
        )
        self.x_dc = Tb6612Channel(
            OutputDevice(TB6612_PINS["bin1"], initial_value=False),
            OutputDevice(TB6612_PINS["bin2"], initial_value=False),
            PWMOutputDevice(TB6612_PINS["pwmb"], frequency=1_000, initial_value=0),
        )
        self.stop_all()

    def enable(self):
        self.stby.on()

    def stop_all(self):
        self.y.stop()
        self.x_dc.stop()
        self.stby.off()

    def close(self):
        self.stop_all()
        self.y.close()
        self.x_dc.close()
        self.stby.close()


class StepDirDriver:
    """Optional external STEP/DIR stepper driver; its GPIOs are not in the supplied map."""

    def __init__(self, step_pin, direction_pin, pulse_seconds):
        from gpiozero import OutputDevice

        self.step = OutputDevice(step_pin, initial_value=False)
        self.direction = OutputDevice(direction_pin, initial_value=False)
        self.pulse_seconds = pulse_seconds

    def move(self, direction, steps):
        self.direction.value = direction > 0
        for _ in range(steps):
            self.step.on()
            time.sleep(self.pulse_seconds)
            self.step.off()
            time.sleep(self.pulse_seconds)

    def close(self):
        self.step.off()
        self.step.close()
        self.direction.close()


@dataclass
class EncoderReading:
    channel: int
    degrees: float | None
    raw: int | None
    status: str


def read_encoders(bus_number, mux_address, sensor_address, channels):
    """Read each AS5600 independently through the PCA9548A."""
    try:
        from smbus2 import SMBus
    except ImportError:
        return [EncoderReading(channel, None, None, "smbus2 unavailable") for channel in channels]

    readings = []
    try:
        with SMBus(bus_number) as bus:
            for channel in channels:
                try:
                    select_channel(bus, mux_address, channel)
                    raw, degrees, status = read_sensor(bus, sensor_address)
                    readings.append(EncoderReading(channel, degrees, raw, status))
                except OSError as error:
                    readings.append(EncoderReading(channel, None, None, f"I2C error: {error}"))
            bus.write_byte(mux_address, 0x00)
    except OSError as error:
        return [EncoderReading(channel, None, None, f"I2C bus error: {error}") for channel in channels]
    return readings


def print_diagnostic(name, passed, detail):
    state = "PASS" if passed else "FAIL"
    print(f"[{state}] {name}: {detail}")


def run_diagnostics(args):
    """Check software, camera, encoder readings, and safe GPIO initialization without movement."""
    print("=== Monitor aim startup diagnostic ===")
    print("Pin map: Y actuator=TB6612 Motor A; TB6612 standby=GPIO 14; I2C=GPIO 2/3.")
    print("Motor electrical movement is deliberately not part of the automatic test.")

    try:
        import cv2

        cap = cv2.VideoCapture(args.camera)
        opened, frame = cap.isOpened(), None
        if opened:
            opened, frame = cap.read()
        cap.release()
        print_diagnostic("camera", bool(opened and frame is not None), f"camera index {args.camera}")
    except ImportError:
        print_diagnostic("camera", False, "OpenCV unavailable")

    readings = read_encoders(args.i2c_bus, args.mux_address, args.sensor_address, args.sensor_channels)
    for reading in readings:
        if reading.degrees is None:
            print_diagnostic(f"AS5600 channel {reading.channel}", False, reading.status)
        else:
            print_diagnostic(
                f"AS5600 channel {reading.channel}",
                reading.status == "magnet OK",
                f"{reading.degrees:.2f} degrees, raw={reading.raw}, {reading.status}",
            )

    if args.enable_motion:
        try:
            driver = Tb6612Driver()
            driver.close()
            print_diagnostic("TB6612 GPIO", True, "all outputs initialized low; STBY remains low")
        except Exception as error:
            print_diagnostic("TB6612 GPIO", False, str(error))
    else:
        print_diagnostic("TB6612 GPIO", True, "dry-run: no GPIO output opened")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--mirror", action="store_true", help="Mirror the camera preview")
    parser.add_argument("--i2c-bus", type=int, default=1, help="I2C bus (default: 1)")
    parser.add_argument("--mux-address", type=lambda value: int(value, 0), default=PCA9548A_DEFAULT_ADDRESS)
    parser.add_argument("--sensor-address", type=lambda value: int(value, 0), default=AS5600_DEFAULT_ADDRESS)
    parser.add_argument("--sensor-channels", type=parse_channels, default=[0, 1, 2])
    parser.add_argument("--test-only", action="store_true", help="Run diagnostics without opening the preview")
    parser.add_argument("--enable-motion", action="store_true", help="Allow motor commands after the diagnostic")
    parser.add_argument(
        "--confirm-y-limits",
        action="store_true",
        help="Confirm that the Y actuator has tested physical end limits before allowing motion",
    )
    parser.add_argument(
        "--x-mode",
        choices=("disabled", "tb6612-dc", "external-step-dir"),
        default="disabled",
        help="X drive type; a standard stepper requires external-step-dir",
    )
    parser.add_argument("--step-pin", type=int, help="STEP GPIO for an external stepper driver")
    parser.add_argument("--direction-pin", type=int, help="DIR GPIO for an external stepper driver")
    parser.add_argument("--step-pulse-ms", type=float, default=2.0, help="External STEP pulse half-period in ms")
    parser.add_argument("--steps-per-screen", type=float, help="Calibrated external-stepper steps for full screen width")
    return parser.parse_args()


def validate_motion_args(args):
    if not args.enable_motion:
        return
    if not args.confirm_y_limits:
        raise SystemExit("Refusing motion: pass --confirm-y-limits only after verifying physical Y end limits.")
    if args.x_mode == "external-step-dir":
        if args.step_pin is None or args.direction_pin is None or not args.steps_per_screen:
            raise SystemExit("external-step-dir requires --step-pin, --direction-pin, and --steps-per-screen.")
        if args.step_pin == args.direction_pin or args.step_pin in TB6612_PINS.values() or args.direction_pin in TB6612_PINS.values():
            raise SystemExit("External stepper pins must be unique and cannot reuse a TB6612 pin.")


def detect_face(cascade, frame, previous):
    gray = frame
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if not len(faces):
        return None, None
    if previous is None:
        x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
    else:
        x, y, width, height = min(
            faces,
            key=lambda face: (face[0] + face[2] / 2 - previous[0]) ** 2 + (face[1] + face[3] / 2 - previous[1]) ** 2,
        )
    return (x + width // 2, y + height // 2), (x, y, width, height)


def run_preview(args):
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        raise SystemExit("Could not load OpenCV's frontal-face cascade")
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}")

    driver = None
    stepper = None
    if args.enable_motion:
        driver = Tb6612Driver()
        driver.enable()
        if args.x_mode == "external-step-dir":
            stepper = StepDirDriver(args.step_pin, args.direction_pin, args.step_pulse_ms / 1000)

    monitor_aim = None
    previous_face = None
    path = deque(maxlen=40)
    y_stop_at = x_stop_at = 0.0
    last_control = last_report = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise SystemExit("Camera frame read failed")
            if args.mirror:
                frame = cv2.flip(frame, 1)
            height, width = frame.shape[:2]
            if monitor_aim is None:
                monitor_aim = [width / 2, height / 2]

            now = time.monotonic()
            if driver and now >= y_stop_at:
                driver.y.stop()
            if driver and now >= x_stop_at:
                driver.x_dc.stop()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            target, face_box = detect_face(cascade, gray, previous_face)
            if target:
                previous_face = target
                path.append(target)
                x, y, box_width, box_height = face_box
                cv2.rectangle(frame, (x, y), (x + box_width, y + box_height), (0, 255, 0), 2)
                if now - last_control >= CONTROL_PERIOD_SECONDS:
                    last_control = now
                    x_error = target[0] - monitor_aim[0]
                    y_error = target[1] - monitor_aim[1]
                    if abs(y_error) > DEAD_ZONE_PIXELS:
                        direction = 1 if y_error > 0 else -1
                        monitor_aim[1] += clamp(y_error, -12, 12)
                        if driver:
                            driver.y.drive(direction, duty_for_error(y_error))
                            y_stop_at = now + MAX_PULSE_SECONDS
                    if abs(x_error) > DEAD_ZONE_PIXELS:
                        direction = 1 if x_error > 0 else -1
                        if args.x_mode == "external-step-dir" and stepper:
                            steps = max(1, min(8, round(abs(x_error) / width * args.steps_per_screen / 8)))
                            stepper.move(direction, steps)
                            monitor_aim[0] += direction * steps / args.steps_per_screen * width
                        elif args.x_mode == "tb6612-dc":
                            monitor_aim[0] += clamp(x_error, -12, 12)
                            if driver:
                                driver.x_dc.drive(direction, duty_for_error(x_error))
                                x_stop_at = now + MAX_PULSE_SECONDS
            else:
                previous_face = None

            if len(path) > 1:
                cv2.polylines(frame, [np.array(path)], False, (0, 140, 0), 2)
            if target:
                draw_crosshair(cv2, frame, target, (0, 255, 0), "FACE TARGET")
            draw_crosshair(cv2, frame, monitor_aim, (255, 255, 0), "ESTIMATED MONITOR AIM")
            if target:
                cv2.line(frame, tuple(map(int, monitor_aim)), target, (255, 0, 255), 1)

            mode = "MOTION ENABLED" if args.enable_motion else "DRY RUN - NO MOTOR OUTPUT"
            cv2.putText(frame, mode, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255) if args.enable_motion else (0, 255, 255), 2)
            cv2.putText(frame, f"X mode: {args.x_mode} | Esc or X: emergency stop", (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)

            if now - last_report >= 2.0:
                last_report = now
                readings = read_encoders(args.i2c_bus, args.mux_address, args.sensor_address, args.sensor_channels)
                encoder_text = ", ".join(
                    f"ch{item.channel}={item.degrees:.2f}°/{item.raw}" if item.degrees is not None else f"ch{item.channel}={item.status}"
                    for item in readings
                )
                face_text = f"face={tuple(map(int, target))}" if target else "face=not detected"
                print(f"{face_text}; estimated_aim=({monitor_aim[0]:.0f}, {monitor_aim[1]:.0f}); {encoder_text}")

            cv2.imshow("Monitor Face Aim", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("x")):
                break
    finally:
        if driver:
            driver.close()
        if stepper:
            stepper.close()
        cap.release()
        cv2.destroyAllWindows()


def main():
    args = parse_args()
    validate_motion_args(args)
    run_diagnostics(args)
    if not args.test_only:
        run_preview(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEmergency stop requested.")
        sys.exit(0)
