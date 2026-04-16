import cv2
import mediapipe as mp
import time  # Added for the 7-second timer
import csv
import os
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

'''
The script will exit on its own after 7 seconds of data collection.
Landmark data will be saved to a CSV file named after the pose (e.g., fist.csv).
'''

# Configuration & Setup
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)
]

POSE = "3"
csv_file = open(f"{POSE}.csv", "a", newline="")
writer = csv.writer(csv_file)

# Timer Setup
DURATION = 12 # Seconds
start_time = time.time()

def draw_landmarks_on_image(image, detection_result):
    if detection_result.hand_landmarks:
        for hand_landmarks in detection_result.hand_landmarks:
            for landmark in hand_landmarks:
                x = int(landmark.x * image.shape[1])
                y = int(landmark.y * image.shape[0])
                cv2.circle(image, (x, y), 5, (0, 255, 0), -1)
            for connection in HAND_CONNECTIONS:
                start_idx, end_idx = connection
                start_landmark = hand_landmarks[start_idx]
                end_landmark = hand_landmarks[end_idx]
                start_point = (int(start_landmark.x * image.shape[1]), int(start_landmark.y * image.shape[0]))
                end_point = (int(end_landmark.x * image.shape[1]), int(end_landmark.y * image.shape[0]))
                cv2.line(image, start_point, end_point, (0, 255, 0), 2)
    return image

# MediaPipe Setup
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, 'hand_landmarker.task')
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5)

cap = cv2.VideoCapture(0)
frame_timestamp_ms = 0

# 2. Main Loop
with vision.HandLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        # Check if 7 seconds have passed
        elapsed_time = time.time() - start_time
        if elapsed_time > DURATION:
            print(f"Time's up! Data collection for {POSE} complete.")
            break

        success, image = cap.read()
        if not success: continue

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        # Save landmarks
        if detection_result.hand_landmarks:
            hand = detection_result.hand_landmarks[0]
            row = []
            for lm in hand:
                row.extend([lm.x, lm.y])
            row.append(POSE)
            writer.writerow(row)

        frame_timestamp_ms += 33
        annotated_image = image.copy()
        annotated_image = draw_landmarks_on_image(annotated_image, detection_result)
        
        # UI: Add Countdown Timer and Pose Name
        remaining = int(DURATION - elapsed_time)
        display_image = cv2.flip(annotated_image, 1)
        cv2.putText(display_image, f"Collecting: {POSE.upper()}", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(display_image, f"Closing in: {remaining}s", (10, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        cv2.imshow('MediaPipe Hands', display_image)
        
        if cv2.waitKey(5) & 0xFF == 27:
            break

# Cleanup
csv_file.close()
cap.release()
cv2.destroyAllWindows()
