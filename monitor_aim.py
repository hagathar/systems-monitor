#!/usr/bin/env python3
"""Diagnose and safely aim a monitor at a detected face on Raspberry Pi."""

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


# Revised, non-conflicting pin maps supplied for the two motor drivers.
# L298N ENA/ENB jumpers are installed, so both channels run at full supply voltage.
L298N_PINS = {"in1": 24, "in2": 22, "in3": 23, "in4": 25}
TB6612_PINS = {
    "pwma": 20,
    "ain1": 5,
    "ain2": 17,
    "stby": 14,
    "bin1": 27,
    "bin2": 16,
    "pwmb": 18,
}

Y_PULSE_SECONDS = 0.06
CONTROL_PERIOD_SECONDS = 0.18
DEAD_ZONE_PIXELS = 24
MAX_STEPS_PER_CONTROL = 8


def validate_pin_maps():
    overlap = set(L298N_PINS.values()) & set(TB6612_PINS.values())
    if overlap:
        raise RuntimeError(f"L298N and TB6612 GPIO maps overlap: {sorted(overlap)}")


def parse_channels(value):
    try:
        channels = [int(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Channels must be comma-separated integers") from error
    if not channels or any(channel not in range(8) for channel in channels):
        raise argparse.ArgumentTypeError("Each PCA9548A channel must be between 0 and 7")
    return channels


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def draw_crosshair(cv2, frame, point, color, label):
    x, y = map(int, point)
    cv2.line(frame, (x - 16, y), (x + 16, y), color, 2)
    cv2.line(frame, (x, y - 16), (x, y + 16), color, 2)
    cv2.circle(frame, (x, y), 5, color, 2)
    cv2.putText(frame, label, (x + 20, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


class L298NActuators:
    """Two parallel Y-axis linear actuators driven by an L298N with EN jumpers."""

    def __init__(self):
        from gpiozero import OutputDevice

        self.in1 = OutputDevice(L298N_PINS["in1"], initial_value=False)
        self.in2 = OutputDevice(L298N_PINS["in2"], initial_value=False)
        self.in3 = OutputDevice(L298N_PINS["in3"], initial_value=False)
        self.in4 = OutputDevice(L298N_PINS["in4"], initial_value=False)
        self.stop()

    def drive_y(self, direction):
        """Move both actuators together; direction is intentionally a short, full-power pulse."""
        forward = direction > 0
        self.in1.value = forward
        self.in2.value = not forward
        self.in3.value = forward
        self.in4.value = not forward

    def stop(self):
        self.in1.off()
        self.in2.off()
        self.in3.off()
        self.in4.off()

    def close(self):
        self.stop()
        self.in1.close()
        self.in2.close()
        self.in3.close()
        self.in4.close()


class Tb6612Coil:
    """One TB6612 H-bridge channel used as one coil of a bipolar stepper."""

    def __init__(self, in1, in2, pwm):
        self.in1 = in1
        self.in2 = in2
        self.pwm = pwm
        self.release()

    def energize(self, polarity):
        self.in1.value = polarity > 0
        self.in2.value = polarity < 0
        self.pwm.value = 1

    def release(self):
        self.pwm.value = 0
        self.in1.off()
        self.in2.off()

    def close(self):
        self.release()
        self.in1.close()
        self.in2.close()
        self.pwm.close()


class Tb6612Stepper:
    """Four-wire bipolar stepper using both TB6612FNG H-bridges."""

    # Full-step sequence: (coil A polarity, coil B polarity).
    SEQUENCE = ((1, 1), (-1, 1), (-1, -1), (1, -1))

    def __init__(self, pulse_seconds):
        from gpiozero import OutputDevice, PWMOutputDevice

        self.stby = OutputDevice(TB6612_PINS["stby"], initial_value=False)
        self.coil_a = Tb6612Coil(
            OutputDevice(TB6612_PINS["ain1"], initial_value=False),
            OutputDevice(TB6612_PINS["ain2"], initial_value=False),
            PWMOutputDevice(TB6612_PINS["pwma"], frequency=1_000, initial_value=0),
        )
        self.coil_b = Tb6612Coil(
            OutputDevice(TB6612_PINS["bin1"], initial_value=False),
            OutputDevice(TB6612_PINS["bin2"], initial_value=False),
            PWMOutputDevice(TB6612_PINS["pwmb"], frequency=1_000, initial_value=0),
        )
        self.pulse_seconds = pulse_seconds
        self.index = 0
        self.release()

    def move(self, direction, steps):
        self.stby.on()
        try:
            for _ in range(steps):
                self.index = (self.index + (1 if direction > 0 else -1)) % len(self.SEQUENCE)
                coil_a, coil_b = self.SEQUENCE[self.index]
                self.coil_a.energize(coil_a)
                self.coil_b.energize(coil_b)
                time.sleep(self.pulse_seconds)
        finally:
            # Do not leave the stepper coils energised and heating between pulses.
            self.release()

    def release(self):
        self.coil_a.release()
        self.coil_b.release()
        self.stby.off()

    def close(self):
        self.release()
        self.coil_a.close()
        self.coil_b.close()
        self.stby.close()


@dataclass
class EncoderReading:
    channel: int
    degrees: float | None
    raw: int | None
    status: str


def read_encoders(bus_number, mux_address, sensor_address, channels):
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
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")


def run_diagnostics(args):
    """Run non-moving checks first: camera, encoders, and motor outputs held low."""
    print("=== Monitor aim startup diagnostic ===")
    print("L298N: Y actuators on GPIO 24/22 and GPIO 23/25; ENA/ENB jumpers installed.")
    print("TB6612: X bipolar stepper coils on GPIO 5/17 and GPIO 27/16.")
    print("Automatic diagnostics never command motor movement.")

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

    for reading in read_encoders(args.i2c_bus, args.mux_address, args.sensor_address, args.sensor_channels):
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
            actuators = L298NActuators()
            stepper = Tb6612Stepper(args.step_pulse_ms / 1000)
            actuators.close()
            stepper.close()
            print_diagnostic("L298N and TB6612 GPIO", True, "all outputs initialized low; TB6612 STBY low")
        except Exception as error:
            print_diagnostic("L298N and TB6612 GPIO", False, str(error))
    else:
        print_diagnostic("motor GPIO", True, "dry-run: no motor GPIO output opened")


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
    parser.add_argument("--confirm-y-limits", action="store_true", help="Confirm tested physical end limits for both Y actuators")
    parser.add_argument("--invert-y", action="store_true", help="Reverse both Y actuator directions")
    parser.add_argument("--invert-x", action="store_true", help="Reverse X stepper direction")
    parser.add_argument("--x-mode", choices=("disabled", "tb6612-stepper"), default="tb6612-stepper")
    parser.add_argument("--step-pulse-ms", type=float, default=4.0, help="Stepper coil dwell per full step in ms (default: 4)")
    parser.add_argument("--steps-per-screen", type=float, help="Calibrated X full-steps for one screen width")
    return parser.parse_args()


def validate_motion_args(args):
    validate_pin_maps()
    if args.step_pulse_ms <= 0:
        raise SystemExit("--step-pulse-ms must be greater than zero")
    if args.test_only or not args.enable_motion:
        return
    if not args.confirm_y_limits:
        raise SystemExit("Refusing motion: pass --confirm-y-limits only after checking the Y actuators' physical limits.")
    if args.x_mode == "tb6612-stepper" and (not args.steps_per_screen or args.steps_per_screen <= 0):
        raise SystemExit("TB6612 stepper motion requires a calibrated --steps-per-screen value.")


def detect_face(cascade, gray, previous):
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

    actuators = stepper = None
    if args.enable_motion:
        actuators = L298NActuators()
        stepper = Tb6612Stepper(args.step_pulse_ms / 1000)

    monitor_aim = previous_face = None
    face_path = deque(maxlen=40)
    y_stop_at = last_control = last_report = 0.0

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
            if actuators and now >= y_stop_at:
                actuators.stop()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            target, face_box = detect_face(cascade, gray, previous_face)
            if target:
                previous_face = target
                face_path.append(target)
                x, y, box_width, box_height = face_box
                cv2.rectangle(frame, (x, y), (x + box_width, y + box_height), (0, 255, 0), 2)

                if now - last_control >= CONTROL_PERIOD_SECONDS:
                    last_control = now
                    x_error = target[0] - monitor_aim[0]
                    y_error = target[1] - monitor_aim[1]
                    if abs(y_error) > DEAD_ZONE_PIXELS:
                        direction = 1 if y_error > 0 else -1
                        if args.invert_y:
                            direction *= -1
                        monitor_aim[1] += clamp(y_error, -12, 12)
                        if actuators:
                            actuators.drive_y(direction)
                            y_stop_at = now + Y_PULSE_SECONDS
                    if abs(x_error) > DEAD_ZONE_PIXELS and args.x_mode == "tb6612-stepper":
                        if stepper:
                            steps = max(1, min(MAX_STEPS_PER_CONTROL, round(abs(x_error) / width * args.steps_per_screen / 8)))
                            direction = 1 if x_error > 0 else -1
                            if args.invert_x:
                                direction *= -1
                            stepper.move(direction, steps)
                            monitor_aim[0] += direction * steps / args.steps_per_screen * width
                        else:
                            # Dry-run visualisation only; real motion requires calibrated steps-per-screen.
                            monitor_aim[0] += clamp(x_error, -12, 12)
            else:
                previous_face = None

            if len(face_path) > 1:
                cv2.polylines(frame, [np.array(face_path, dtype=np.int32)], False, (0, 140, 0), 2)
            if target:
                draw_crosshair(cv2, frame, target, (0, 255, 0), "FACE TARGET")
            draw_crosshair(cv2, frame, monitor_aim, (255, 255, 0), "ESTIMATED MONITOR AIM")
            if target:
                cv2.line(frame, tuple(map(int, monitor_aim)), target, (255, 0, 255), 1)

            mode = "MOTION ENABLED" if args.enable_motion else "DRY RUN - NO MOTOR OUTPUT"
            color = (0, 0, 255) if args.enable_motion else (0, 255, 255)
            cv2.putText(frame, mode, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            cv2.putText(frame, f"X: {args.x_mode} | Y: L298N dual actuator | Esc/Q/X: stop", (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

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
            if cv2.waitKey(1) & 0xFF in (27, ord("q"), ord("x")):
                break
    finally:
        if actuators:
            actuators.close()
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
