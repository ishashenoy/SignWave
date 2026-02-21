import torch
import torch.nn as nn
import cv2
import mediapipe as mp
from collections import deque
import os
import numpy as np
import time
import random
import math

# -------------------------
# 1. Model Setup
# -------------------------
class PoseNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(42, 64)
        self.relu1 = nn.ReLU(); self.dropout1 = nn.Dropout(0.2)
        self.fc2 = nn.Linear(64, 32)
        self.relu2 = nn.ReLU(); self.dropout2 = nn.Dropout(0.2)
        self.fc3 = nn.Linear(32, 5)
    def forward(self, x):
        x = self.dropout1(self.relu1(self.fc1(x)))
        x = self.dropout2(self.relu2(self.fc2(x)))
        return self.fc3(x)

model = PoseNet()
model.load_state_dict(torch.load("pose_model.pt", weights_only=True))
model.eval()

# -------------------------
# 2. Pose Icons/Sprites - Load from assets
# -------------------------
def load_and_process_icon(pose_name, size=120):
    """Load PNG icon from assets/poses and apply colorful background"""
    # Load the PNG file
    assets_path = "assets/poses"
    icon_path = os.path.join(assets_path, f"{pose_name}.png")
    
    # Try to load the image
    loaded_img = cv2.imread(icon_path, cv2.IMREAD_UNCHANGED)
    
    if loaded_img is None:
        # Fallback: create a simple placeholder if file not found
        print(f"Warning: Could not load {icon_path}, using placeholder")
        icon = np.zeros((size, size, 3), dtype=np.uint8)
        cv2.putText(icon, pose_name.upper(), (10, size // 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        return icon
    
    # Define colors for each pose (BGR format)
    colors = {
        "palm": (60, 180, 255),    # Orange
        "1": (255, 100, 255),       # Magenta
        "2": (255, 255, 100),       # Cyan
        "3": (100, 255, 100),       # Green
        "fist": (100, 100, 255)     # Red
    }
    
    base_color = colors.get(pose_name, (200, 200, 200))
    
    # Create background with gradient circle
    icon = np.zeros((size, size, 3), dtype=np.uint8)
    center_pos = size // 2
    
    for i in range(size):
        for j in range(size):
            dist = math.sqrt((i - center_pos)**2 + (j - center_pos)**2)
            if dist < size // 2 - 5:
                intensity = 1 - (dist / (size // 2))
                color = tuple(int(c * intensity) for c in base_color)
                icon[i, j] = color
    
    # Add outer glow ring
    cv2.circle(icon, (center_pos, center_pos), size // 2 - 5, base_color, 8)
    cv2.circle(icon, (center_pos, center_pos), size // 2 - 10, (255, 255, 255), 3)
    
    # Resize the loaded icon to fit (keep aspect ratio)
    icon_size = int(size * 0.6)  # Icon takes up 60% of the circle
    h, w = loaded_img.shape[:2]
    aspect = w / h
    
    if aspect > 1:
        new_w = icon_size
        new_h = int(icon_size / aspect)
    else:
        new_h = icon_size
        new_w = int(icon_size * aspect)
    
    resized = cv2.resize(loaded_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # Calculate position to center the icon
    x_offset = center_pos - new_w // 2
    y_offset = center_pos - new_h // 2
    
    # Overlay the icon on the background
    if resized.shape[2] == 4:  # Has alpha channel
        # Extract alpha channel
        alpha = resized[:, :, 3] / 255.0
        
        # Get the region of interest
        for c in range(3):
            icon[y_offset:y_offset+new_h, x_offset:x_offset+new_w, c] = \
                (alpha * resized[:, :, c] + 
                 (1 - alpha) * icon[y_offset:y_offset+new_h, x_offset:x_offset+new_w, c])
    else:
        # No alpha channel, just paste it
        icon[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized[:, :, :3]
    
    # Add pose name at bottom
    name_text = pose_name.upper()
    name_size = cv2.getTextSize(name_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
    name_x = center_pos - name_size[0] // 2
    cv2.putText(icon, name_text, (name_x + 1, size - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
    cv2.putText(icon, name_text, (name_x, size - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    
    return icon

def create_pose_icon(pose_name, size=120):
    """Load and create colorful icon for each pose"""
    return load_and_process_icon(pose_name, size)

# -------------------------
# 3. Note/Beat Class
# -------------------------
class Note:
    def __init__(self, pose_idx, spawn_time, lane_x, hit_y, speed=200):
        self.pose_idx = pose_idx
        self.spawn_time = spawn_time
        self.lane_x = lane_x
        self.hit_y = hit_y
        self.speed = speed  # pixels per second
        self.start_y = -100
        self.current_y = self.start_y
        self.hit = False
        self.missed = False
        self.hit_time = None
        
    def update(self, current_time):
        """Update note position"""
        elapsed = current_time - self.spawn_time
        self.current_y = self.start_y + (self.speed * elapsed)
        
        # Check if missed (passed hit zone)
        if self.current_y > self.hit_y + 100 and not self.hit:
            self.missed = True
    
    def is_in_hit_zone(self, tolerance=80):
        """Check if note is in the hit zone"""
        return abs(self.current_y - self.hit_y) < tolerance
    
    def get_hit_accuracy(self):
        """Return hit accuracy (perfect, good, ok, miss)"""
        distance = abs(self.current_y - self.hit_y)
        if distance < 30:
            return "PERFECT"
        elif distance < 50:
            return "GOOD"
        elif distance < 80:
            return "OK"
        else:
            return "MISS"

# -------------------------
# 4. Game State
# -------------------------
poses = ["palm", "1", "2", "3", "fist"]
pose_icons = {pose: create_pose_icon(pose) for pose in poses}

# Game settings
LANE_WIDTH = 140
HIT_ZONE_Y = 550
SPAWN_INTERVAL = 2.0  # seconds between notes
NOTE_SPEED = 200  # pixels per second

# Game state
score = 0
combo = 0
max_combo = 0
notes = []
last_spawn = 0
game_start_time = None
hit_effects = []  # For visual feedback
accuracy_counts = {"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": 0}

history = deque(maxlen=5)

# -------------------------
# 5. UI Helper Functions
# -------------------------
def draw_lane(img, x, width, height, color=(80, 80, 100)):
    """Draw a rhythm lane"""
    overlay = img.copy()
    # Semi-transparent lane
    cv2.rectangle(overlay, (x - width//2, 0), (x + width//2, height), color, -1)
    cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
    
    # Lane borders
    cv2.line(img, (x - width//2, 0), (x - width//2, height), (150, 150, 150), 2)
    cv2.line(img, (x + width//2, 0), (x + width//2, height), (150, 150, 150), 2)

def draw_hit_zone(img, center_x, y, width, active=False):
    """Draw the hit zone indicator"""
    color = (100, 255, 100) if active else (200, 200, 200)
    thickness = 5 if active else 3
    
    # Main hit line
    cv2.line(img, (center_x - width//2, y), (center_x + width//2, y), color, thickness)
    
    # Judgment area indicator
    overlay = img.copy()
    cv2.rectangle(overlay, (center_x - width//2, y - 40), (center_x + width//2, y + 40), color, -1)
    cv2.addWeighted(overlay, 0.2, img, 0.8, 0, img)
    
    # Corner brackets
    bracket_size = 30
    cv2.line(img, (center_x - width//2, y - 40), (center_x - width//2 + bracket_size, y - 40), color, 3)
    cv2.line(img, (center_x - width//2, y - 40), (center_x - width//2, y - 40 + bracket_size), color, 3)
    
    cv2.line(img, (center_x + width//2, y - 40), (center_x + width//2 - bracket_size, y - 40), color, 3)
    cv2.line(img, (center_x + width//2, y - 40), (center_x + width//2, y - 40 + bracket_size), color, 3)
    
    cv2.line(img, (center_x - width//2, y + 40), (center_x - width//2 + bracket_size, y + 40), color, 3)
    cv2.line(img, (center_x - width//2, y + 40), (center_x - width//2, y + 40 - bracket_size), color, 3)
    
    cv2.line(img, (center_x + width//2, y + 40), (center_x + width//2 - bracket_size, y + 40), color, 3)
    cv2.line(img, (center_x + width//2, y + 40), (center_x + width//2, y + 40 - bracket_size), color, 3)

def draw_note(img, note, icon, glow=False):
    """Draw a scrolling note"""
    icon_size = 100
    x = int(note.lane_x - icon_size // 2)
    y = int(note.current_y - icon_size // 2)
    
    # Skip if off screen
    if y + icon_size < 0 or y > img.shape[0]:
        return
    
    # Add glow effect if in hit zone
    if glow and note.is_in_hit_zone():
        glow_overlay = img.copy()
        cv2.circle(glow_overlay, (int(note.lane_x), int(note.current_y)), icon_size // 2 + 20, 
                  (255, 255, 255), -1)
        cv2.addWeighted(glow_overlay, 0.3, img, 0.7, 0, img)
    
    # Ensure icon fits on screen
    icon_h, icon_w = icon.shape[:2]
    
    # Calculate visible region
    src_y1 = max(0, -y)
    src_y2 = min(icon_h, img.shape[0] - y)
    src_x1 = max(0, -x)
    src_x2 = min(icon_w, img.shape[1] - x)
    
    dst_y1 = max(0, y)
    dst_y2 = dst_y1 + (src_y2 - src_y1)
    dst_x1 = max(0, x)
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    
    if src_y2 > src_y1 and src_x2 > src_x1:
        # Blend icon with background
        icon_region = icon[src_y1:src_y2, src_x1:src_x2]
        bg_region = img[dst_y1:dst_y2, dst_x1:dst_x2]
        
        # Create mask for circular blend
        mask = np.zeros((src_y2 - src_y1, src_x2 - src_x1), dtype=np.uint8)
        center = (mask.shape[1] // 2, mask.shape[0] // 2)
        radius = min(mask.shape[0], mask.shape[1]) // 2
        cv2.circle(mask, center, radius, 255, -1)
        
        # Alpha blend
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) / 255.0
        blended = (icon_region * mask_3ch + bg_region * (1 - mask_3ch)).astype(np.uint8)
        img[dst_y1:dst_y2, dst_x1:dst_x2] = blended

def draw_hit_effect(img, x, y, accuracy, age):
    """Draw hit effect animation"""
    colors = {
        "PERFECT": (255, 255, 100),
        "GOOD": (100, 255, 100),
        "OK": (100, 200, 255),
        "MISS": (100, 100, 255)
    }
    
    color = colors.get(accuracy, (200, 200, 200))
    alpha = 1 - (age / 0.8)  # Fade out over 0.8 seconds
    
    if alpha > 0:
        # Expanding ring
        radius = int(30 + age * 100)
        overlay = img.copy()
        cv2.circle(overlay, (int(x), int(y)), radius, color, 5)
        cv2.addWeighted(overlay, alpha * 0.5, img, 1 - alpha * 0.5, 0, img)
        
        # Text
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(accuracy, font, 1.0, 2)[0]
        text_x = int(x - text_size[0] // 2)
        text_y = int(y - 50 - age * 30)  # Float upward
        
        text_color = tuple(int(c * alpha) for c in color)
        cv2.putText(img, accuracy, (text_x + 2, text_y + 2), font, 1.0, (0, 0, 0), 3)
        cv2.putText(img, accuracy, (text_x, text_y), font, 1.0, text_color, 2)

def draw_combo(img, combo, x, y):
    """Draw combo counter"""
    if combo > 1:
        combo_text = f"{combo} COMBO"
        
        # Combo color based on value
        if combo < 10:
            color = (255, 255, 100)
        elif combo < 20:
            color = (100, 255, 255)
        else:
            color = (255, 100, 255)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.5 if combo % 5 == 0 else 1.2  # Pulse on milestones
        
        text_size = cv2.getTextSize(combo_text, font, scale, 3)[0]
        text_x = x - text_size[0] // 2
        
        cv2.putText(img, combo_text, (text_x + 3, y + 3), font, scale, (0, 0, 0), 4)
        cv2.putText(img, combo_text, (text_x, y), font, scale, color, 3)

# -------------------------
# 6. MediaPipe Setup
# -------------------------
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, "hand_landmarker.task")
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options, running_mode=vision.RunningMode.VIDEO,
    num_hands=1, min_hand_detection_confidence=0.5
)

cap = cv2.VideoCapture(0)
frame_timestamp_ms = 0

# -------------------------
# 7. Main Game Loop
# -------------------------
with vision.HandLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        success, image = cap.read()
        if not success: 
            break
        
        current_time = time.time()
        
        # Initialize game timer
        if game_start_time is None:
            game_start_time = current_time
            last_spawn = current_time
        
        game_time = current_time - game_start_time
        
        # --- SPAWN NEW NOTES ---
        if current_time - last_spawn > SPAWN_INTERVAL:
            pose_idx = random.randint(0, 4)
            h, w, _ = image.shape
            lane_x = w - LANE_WIDTH  # Right side lane
            
            note = Note(pose_idx, current_time, lane_x, HIT_ZONE_Y, NOTE_SPEED)
            notes.append(note)
            last_spawn = current_time
        
        # --- HAND DETECTION ---
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = landmarker.detect_for_video(mp_image, int(frame_timestamp_ms))
        frame_timestamp_ms += 33
        
        predicted_pose_idx = None
        predicted_pose = "..."
        confidence = 0.0
        
        if detection_result.hand_landmarks:
            hand = detection_result.hand_landmarks[0]
            raw = []
            for lm in hand: 
                raw.extend([lm.x, lm.y])
            
            wrist_x, wrist_y = raw[0], raw[1]
            nx = [raw[i] - wrist_x for i in range(0, 42, 2)]
            ny = [raw[i] - wrist_y for i in range(1, 42, 2)]
            combined = nx + ny
            max_val = max(abs(max(combined)), abs(min(combined)))
            
            if max_val > 0:
                input_data = torch.tensor([[v/max_val for v in combined]], dtype=torch.float32)
                with torch.no_grad():
                    preds = model(input_data)
                    prob = torch.softmax(preds, dim=1)
                    confidence = prob.max().item()
                    idx = torch.argmax(preds).item()
                    
                    if confidence > 0.80:
                        history.append(idx)
                    else:
                        history.clear()
            
            if history:
                predicted_pose_idx = max(set(history), key=history.count)
                predicted_pose = poses[predicted_pose_idx]
        
        # --- UPDATE NOTES ---
        active_notes = []
        for note in notes:
            note.update(current_time)
            
            # Check for hit
            if not note.hit and not note.missed and note.is_in_hit_zone():
                if predicted_pose_idx == note.pose_idx:
                    accuracy = note.get_hit_accuracy()
                    note.hit = True
                    note.hit_time = current_time
                    
                    # Update score based on accuracy
                    points = {"PERFECT": 100, "GOOD": 75, "OK": 50, "MISS": 0}
                    score += points.get(accuracy, 0)
                    
                    combo += 1
                    max_combo = max(max_combo, combo)
                    accuracy_counts[accuracy] += 1
                    
                    # Add hit effect
                    hit_effects.append({
                        'x': note.lane_x,
                        'y': note.current_y,
                        'accuracy': accuracy,
                        'time': current_time
                    })
            
            # Check for miss
            if note.missed and not note.hit:
                combo = 0
                accuracy_counts["MISS"] += 1
                hit_effects.append({
                    'x': note.lane_x,
                    'y': HIT_ZONE_Y,
                    'accuracy': "MISS",
                    'time': current_time
                })
            
            # Keep note if still visible or just hit
            if note.current_y < image.shape[0] + 100 or (note.hit and current_time - note.hit_time < 0.5):
                if not note.missed:
                    active_notes.append(note)
        
        notes = active_notes
        
        # --- RENDER ---
        flipped = cv2.flip(image, 1)
        h, w, _ = flipped.shape
        
        # Draw lane (with dark background only in lane area) - positioned on the right
        lane_x = w - LANE_WIDTH  # Position lane on the right side
        # Draw dark overlay only on the lane
        overlay = flipped.copy()
        cv2.rectangle(overlay, (lane_x - LANE_WIDTH//2, 0), (lane_x + LANE_WIDTH//2, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, flipped, 0.5, 0, flipped)
        
        draw_lane(flipped, lane_x, LANE_WIDTH, h)
        
        # Draw hit zone
        in_hit_zone = any(note.is_in_hit_zone() for note in notes)
        draw_hit_zone(flipped, lane_x, HIT_ZONE_Y, LANE_WIDTH, in_hit_zone)
        
        # Draw notes
        for note in notes:
            icon = pose_icons[poses[note.pose_idx]]
            glow = predicted_pose_idx == note.pose_idx
            draw_note(flipped, note, icon, glow)
        
        # Draw hit effects
        hit_effects = [e for e in hit_effects if current_time - e['time'] < 0.8]
        for effect in hit_effects:
            age = current_time - effect['time']
            draw_hit_effect(flipped, effect['x'], effect['y'], effect['accuracy'], age)
        
        # Draw combo
        if combo > 1:
            draw_combo(flipped, combo, w - LANE_WIDTH, 100)
        
        # --- HUD ---
        # Score panel (top left)
        cv2.rectangle(flipped, (10, 10), (250, 120), (40, 40, 40), -1)
        cv2.rectangle(flipped, (10, 10), (250, 120), (100, 100, 100), 3)
        
        cv2.putText(flipped, f"SCORE: {score}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(flipped, f"MAX COMBO: {max_combo}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(flipped, f"TIME: {int(game_time)}s", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # Current pose detection (bottom)
        pose_panel_h = 80
        cv2.rectangle(flipped, (0, h - pose_panel_h), (w, h), (30, 30, 30), -1)
        
        pose_color = (100, 255, 100) if predicted_pose_idx is not None else (200, 200, 200)
        cv2.putText(flipped, f"CURRENT POSE: {predicted_pose.upper()}", (20, h - 45), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, pose_color, 2)
        
        # Confidence bar
        conf_w = 300
        conf_x = 20
        conf_y = h - 20
        cv2.rectangle(flipped, (conf_x, conf_y), (conf_x + conf_w, conf_y + 15), (50, 50, 50), -1)
        if confidence > 0:
            cv2.rectangle(flipped, (conf_x, conf_y), (conf_x + int(conf_w * confidence), conf_y + 15), 
                         (100, 255, 100), -1)
        cv2.putText(flipped, f"{int(confidence * 100)}%", (conf_x + conf_w + 10, conf_y + 12), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Instructions (first 10 seconds)
        if game_time < 10:
            instruction = "Hold the matching pose when the icon reaches the hit zone!"
            text_size = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            text_x = w // 2 - text_size[0] // 2
            cv2.putText(flipped, instruction, (text_x + 2, 182), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(flipped, instruction, (text_x, 180), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 100), 2)
        
        cv2.imshow("SignWave", flipped)
        if cv2.waitKey(5) & 0xFF == 27: 
            break

cap.release()
cv2.destroyAllWindows()

print(f"\n=== GAME OVER ===")
print(f"Final Score: {score}")
print(f"Max Combo: {max_combo}")
print(f"Total Time: {int(game_time)}s")
print(f"\nAccuracy Breakdown:")
print(f"  Perfect: {accuracy_counts['PERFECT']}")
print(f"  Good: {accuracy_counts['GOOD']}")
print(f"  OK: {accuracy_counts['OK']}")
print(f"  Miss: {accuracy_counts['MISS']}")