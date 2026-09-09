#!/usr/bin/env python3
"""Live webcam face tracker with a visible movement history and heading."""

import argparse
import math
import time
from collections import deque

import cv2
import numpy as np


WINDOW_NAME = "Pi Face Tracker"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Track a face and draw its past path and current heading."
    )
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument(
        "--history", type=int, default=60,
        help="Number of detected positions to retain (default: 60)",
    )
    parser.add_argument(
        "--mirror", action="store_true", help="Mirror the preview horizontally"
    )
    return parser.parse_args()


def choose_face(faces, previous_center):
    """Prefer continuity; otherwise use the largest detected face."""
    if previous_center is None:
        return max(faces, key=lambda face: face[2] * face[3])

    def distance_squared(face):
        x, y, width, height = face
        center = (x + width / 2, y + height / 2)
        return (center[0] - previous_center[0]) ** 2 + (
            center[1] - previous_center[1]
        ) ** 2

    return min(faces, key=distance_squared)


def calculate_heading(points, samples=8):
    """Return a smoothed screen-space velocity from the recent path."""
    if len(points) < 2:
        return 0.0, 0.0

    recent = list(points)[-min(samples, len(points)) :]
    start_x, start_y = recent[0]
    end_x, end_y = recent[-1]
    divisor = max(len(recent) - 1, 1)
    return (end_x - start_x) / divisor, (end_y - start_y) / divisor


def draw_path(frame, points):
    """Draw where the face has been, where it is, and where it is heading."""
    if not points:
        return 0.0, 0.0

    path = list(points)
    if len(path) > 1:
        cv2.polylines(frame, [np.array(path, dtype=np.int32)], False, (0, 180, 0), 2)

    # Small dots preserve the individual historical positions when movement is slow.
    for point in path[:-1]:
        cv2.circle(frame, point, 3, (0, 120, 0), -1)

    current = path[-1]
    velocity_x, velocity_y = calculate_heading(path)
    cv2.circle(frame, current, 8, (0, 0, 255), -1)

    magnitude = math.hypot(velocity_x, velocity_y)
    if magnitude >= 0.5:
        scale = min(90, max(35, magnitude * 12)) / magnitude
        target = (
            int(current[0] + velocity_x * scale),
            int(current[1] + velocity_y * scale),
        )
        cv2.arrowedLine(frame, current, target, (0, 255, 255), 3, tipLength=0.25)

    return velocity_x, velocity_y


def main():
    args = parse_args()
    if args.history < 2:
        raise SystemExit("--history must be at least 2")

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise SystemExit(f"Could not load face cascade: {cascade_path}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {args.camera}")

    positions = deque(maxlen=args.history)
    previous_center = None
    previous_time = time.monotonic()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read a frame from the camera.")
                break
            if args.mirror:
                frame = cv2.flip(frame, 1)

            height, width = frame.shape[:2]
            center_x, center_y = width // 2, height // 2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )

            if len(faces):
                x, y, face_width, face_height = choose_face(faces, previous_center)
                current = (x + face_width // 2, y + face_height // 2)
                positions.append(current)
                previous_center = current

                pan = max(min((current[0] - center_x) / center_x, 1), -1)
                tilt = max(min((current[1] - center_y) / center_y, 1), -1)
                cv2.rectangle(frame, (x, y), (x + face_width, y + face_height), (0, 255, 0), 2)
            else:
                pan = tilt = 0.0
                previous_center = None

            velocity_x, velocity_y = draw_path(frame, positions)
            cv2.circle(frame, (center_x, center_y), 5, (255, 255, 0), -1)

            now = time.monotonic()
            fps = 1 / max(now - previous_time, 0.0001)
            previous_time = now
            status = "FACE FOUND" if len(faces) else "NO FACE"
            cv2.putText(frame, status, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Position  PAN={pan:+.2f}  TILT={tilt:+.2f}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Heading   X={velocity_x:+.1f}  Y={velocity_y:+.1f} px/frame", (20, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"FPS: {fps:.0f}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            if len(faces):
                print(f"PAN={pan:+.2f} TILT={tilt:+.2f} HEADING=({velocity_x:+.1f}, {velocity_y:+.1f})")

            cv2.imshow(WINDOW_NAME, frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
