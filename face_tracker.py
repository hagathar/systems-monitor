import cv2
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    for (x, y, fw, fh) in faces:

        # Face center
        fx = x + fw // 2
        fy = y + fh // 2

        # Offset from screen center
        offset_x = fx - center_x
        offset_y = fy - center_y

        # Normalized values (-1 to 1)
        norm_x = max(min(offset_x / center_x, 1), -1)
        norm_y = max(min(offset_y / center_y, 1), -1)

        # Draw face rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + fw, y + fh),
            (0, 255, 0),
            2
        )

        # Draw tracking point
        cv2.circle(frame, (fx, fy), 8, (0, 0, 255), -1)

        # Draw center line
        cv2.line(
            frame,
            (center_x, center_y),
            (fx, fy),
            (255, 0, 255),
            2
        )

        # Output tracking values
        print(f"PAN={norm_x:.2f} TILT={norm_y:.2f}")

        break

    # FPS display
    fps = 1 / (time.time() - prev_time)
    prev_time = time.time()

    cv2.putText(
        frame,
        f"FPS: {int(fps)}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        2
    )

    # Draw screen center
    cv2.circle(frame, (center_x, center_y), 5, (255, 255, 0), -1)

    # Preview window
    cv2.imshow("Pi5 Face Tracker", frame)

    # ESC to exit
    if cv2.waitKey(1) == 27:
        break

# ---------------------------------
# CLEANUP
# ---------------------------------

cap.release()
cv2.destroyAllWindows()