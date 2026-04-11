from flask import Flask, render_template, Response, request
import cv2
import numpy as np
from ultralytics import YOLO
import threading
import time


# ---------------- CONFIG ----------------
HIGH_CROWD_FRAME_THRESHOLD = 15   # frames for alert

# ---------------------------------------
app = Flask(__name__)

# Load YOLO model
model = YOLO("yolov8n.pt")

# Shared frame (latest from ESP32)
latest_frame = None
lock = threading.Lock()

high_crowd_frames = 0


# ---------------- RECEIVE IMAGE ----------------
@app.route("/upload", methods=["POST"])
def upload():

    global latest_frame

    if "image" not in request.files:
        return "No image", 400

    file = request.files["image"]
    img_bytes = file.read()

    np_arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return "Invalid image", 400

    with lock:
        latest_frame = frame.copy()

    return "Image received", 200


# ---------------- PROCESS + STREAM ----------------
def generate_frames():

    global high_crowd_frames

    heatmap_accumulator = None

    while True:

        with lock:
            if latest_frame is None:
                continue
            frame = latest_frame.copy()

        h, w, _ = frame.shape

        if heatmap_accumulator is None:
            heatmap_accumulator = np.zeros((h, w), dtype=np.float32)

        # -------- YOLO Detection --------
        results = model(frame, classes=[0])
        count = 0

        for r in results:
            for box in r.boxes:

                count += 1

                x1, y1, x2, y2 = map(int, box.xyxy[0])

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                cv2.circle(heatmap_accumulator, (cx, cy), 40, 1, -1)
                cv2.rectangle(frame, (x1, y1), (x2, y2),
                              (0, 255, 0), 2)

        # -------- Heatmap --------
        heatmap_accumulator *= 0.95

        heatmap_norm = cv2.normalize(
            heatmap_accumulator,
            None,
            0, 255,
            cv2.NORM_MINMAX
        ).astype(np.uint8)

        heatmap_color = cv2.applyColorMap(
            heatmap_norm,
            cv2.COLORMAP_JET
        )

        overlay = cv2.addWeighted(
            frame, 0.6,
            heatmap_color, 0.4,
            0
        )

        # -------- Crowd Logic --------
        if count < 1:

            level = "LOW"
            color = (0, 255, 0)
            high_crowd_frames = 0

        elif count < 3:

            level = "MEDIUM"
            color = (0, 165, 255)
            high_crowd_frames = 0

        else:

            level = "HIGH"
            color = (0, 0, 255)
            high_crowd_frames += 1

            cv2.putText(
                overlay,
                f"High Frames: {high_crowd_frames}",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            if high_crowd_frames >= HIGH_CROWD_FRAME_THRESHOLD:

                cv2.putText(
                    overlay,
                    "⚠ ALERT: CROWD OVERLOAD ⚠",
                    (40, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (0, 0, 255),
                    3
                )

        # -------- Info Text --------
        cv2.putText(
            overlay,
            f"People: {count} | Crowd: {level}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            color,
            2
        )

        # -------- Stream --------
        _, buffer = cv2.imencode(".jpg", overlay)

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame_bytes +
            b"\r\n"
        )

        time.sleep(0.03)   # ~30 FPS


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return """
    <html>
    <head><title>Crowd Analyzer</title></head>
    <body style="text-align:center; background:#111; color:white;">
        <h1> Crowd Analyzer Dashboard </h1>
        <img src="/video" width="800">
    </body>
    </html>
    """


@app.route("/video")
def video():

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ---------------- MAIN ----------------
if __name__ == "__main__":

    print(" Crowd Analyzer Server Started")

    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True
    )
