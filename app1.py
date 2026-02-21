from flask import Flask, render_template, Response, request, redirect, url_for, session, jsonify
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
import pygame
import json
import csv
import io

import database as db

app = Flask(__name__)
app.secret_key = 'flowstate_rhythm_game_secret_key_2026'  # Required for session management

# -------------------------
# 1. Audio Setup
# -------------------------
pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

def generate_tone(frequency, duration=0.2, volume=0.3):
    """Generate a simple sine wave tone"""
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    
    # Generate sine wave
    samples = np.sin(2 * np.pi * np.arange(n_samples) * frequency / sample_rate)
    
    # Apply fade out to prevent clicks
    fade_len = int(sample_rate * 0.05)  # 50ms fade
    fade_out = np.linspace(1, 0, fade_len)
    samples[-fade_len:] *= fade_out
    
    # Convert to 16-bit integers
    samples = (samples * volume * 32767).astype(np.int16)
    
    # Create stereo sound (duplicate mono to stereo)
    stereo_samples = np.column_stack((samples, samples))
    
    return pygame.sndarray.make_sound(stereo_samples)

# Musical notes (frequencies in Hz)
# Pose mapping: palm=0(F), 1(C), 2(D), 3(E), fist=4(G)
AUDIO_NOTES = {
    0: generate_tone(349.23),  # F4 - palm
    1: generate_tone(261.63),  # C4 - 1 finger
    2: generate_tone(293.66),  # D4 - 2 fingers
    3: generate_tone(329.63),  # E4 - 3 fingers
    4: generate_tone(392.00),  # G4 - fist
}

# -------------------------
# 2. Model Setup
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
# 3. Pose Icons/Sprites - Load from assets
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
# 4. Note/Beat Class
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
        self.missed = False          # True once we register a miss
        self.hit_time = None
        self.audio_played = False    # Track if audio has been played for this note
        self.incorrect_shown = False # Track if incorrect feedback shown
        
    def update(self, current_time):
        """Update note position based on elapsed time.
        NOTE: Miss detection is handled in the game loop, not here,
        to keep all scoring logic in one place."""
        elapsed = current_time - self.spawn_time
        self.current_y = self.start_y + (self.speed * elapsed)
    
    def is_in_hit_zone(self, tolerance=80):
        """Check if note is in the hit zone"""
        return abs(self.current_y - self.hit_y) < tolerance
    
    def has_passed_hit_zone(self, margin=80):
        """Check if note has fallen past the hit zone by `margin` pixels.
        Used by the game loop to decide when a note counts as missed."""
        return self.current_y > (self.hit_y + margin)
    
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
# 5. Game State
# -------------------------
poses = ["palm", "1", "2", "3", "fist"]
pose_icons = {pose: create_pose_icon(pose) for pose in poses}

# Game settings
LANE_WIDTH = 140
# HIT_ZONE_Y is set dynamically in generate_frames() based on actual camera height.
# Using a placeholder here; the real value is computed as int(frame_height * 0.72).
HIT_ZONE_Y = 350
SPAWN_INTERVAL = 2.0  # Default seconds between notes (used as fallback)
NOTE_SPEED = 200  # pixels per second

# Game state
score = 0
combo = 0
max_combo = 0
notes = []
last_spawn = 0
game_start_time = None
hit_effects = []  # For visual feedback
incorrect_effects = []  # For incorrect pose visual feedback
accuracy_counts = {"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": 0}
next_spawn_delay = SPAWN_INTERVAL  # Dynamic delay for next note spawn

# Accuracy tracking
successful_hits = 0  # Total successful hits (any accuracy level)
total_attempts = 0   # Total notes attempted (hits + misses)
miss_effects = []    # Visual effects for missed notes

# Freestyle mode state
freestyle_mode = False
last_freestyle_pose = None  # Track last pose to detect changes
last_audio_time = 0  # Track when audio was last played
current_playing_note = None  # Currently playing audio note

history = deque(maxlen=5)

# ──────────────────────────────────────────────────
# Rehab Tracking State
# ──────────────────────────────────────────────────
current_session_id = None       # DB session ID for current play-through
note_counter = 0                # Sequential index for notes in a session
last_raw_landmarks = None       # Latest 21-landmark list from MediaPipe
session_joint_deviations = []   # Collect all per-note deviations for averaging
song_complete = False            # True once the song has ended and session is finalized


def normalize_landmarks(raw_42):
    """Convert raw 42-element list to 21 {x, y} dicts, wrist-normalized and scaled."""
    wrist_x, wrist_y = raw_42[0], raw_42[1]
    nx = [raw_42[i] - wrist_x for i in range(0, 42, 2)]
    ny = [raw_42[i] - wrist_y for i in range(1, 42, 2)]
    combined = nx + ny
    max_val = max(abs(max(combined)), abs(min(combined)), 1e-6)
    return [{"x": round(nx[i] / max_val, 5), "y": round(ny[i] / max_val, 5)} for i in range(21)]


def compute_joint_deviations(detected_landmarks, ideal_landmarks):
    """Compute per-joint Euclidean deviation between detected and ideal.
    Both inputs are 21-element lists of {x, y} dicts (normalized).
    Returns a list of 21 floats."""
    if not detected_landmarks or not ideal_landmarks:
        return [None] * 21
    deviations = []
    for i in range(21):
        dx = detected_landmarks[i]["x"] - ideal_landmarks[i]["x"]
        dy = detected_landmarks[i]["y"] - ideal_landmarks[i]["y"]
        deviations.append(round(math.sqrt(dx * dx + dy * dy), 5))
    return deviations


def get_joint_color(deviation, threshold_good=0.08, threshold_ok=0.18):
    """Return BGR color based on deviation: green < good < yellow < ok < red."""
    if deviation is None:
        return (128, 128, 128)  # gray
    if deviation < threshold_good:
        return (0, 255, 0)      # green
    elif deviation < threshold_ok:
        return (0, 255, 255)    # yellow
    else:
        return (0, 0, 255)      # red


def draw_hand_skeleton(img, landmarks_xy, deviations=None, offset_x=0, offset_y=0, scale=1.0):
    """Draw hand skeleton overlay on the image.
    landmarks_xy: list of 21 (pixel_x, pixel_y) tuples.
    deviations: optional 21-element deviation list for color coding."""
    if not landmarks_xy or len(landmarks_xy) < 21:
        return

    # MediaPipe hand connections
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),       # thumb
        (0, 5), (5, 6), (6, 7), (7, 8),       # index
        (0, 9), (9, 10), (10, 11), (11, 12),  # middle
        (0, 13), (13, 14), (14, 15), (15, 16), # ring
        (0, 17), (17, 18), (18, 19), (19, 20), # pinky
        (5, 9), (9, 13), (13, 17),             # palm
    ]

    # Draw connections
    for a, b in connections:
        pt1 = (int(landmarks_xy[a][0]), int(landmarks_xy[a][1]))
        pt2 = (int(landmarks_xy[b][0]), int(landmarks_xy[b][1]))
        cv2.line(img, pt1, pt2, (200, 200, 200), 2)

    # Draw joints with color coding
    for i, (px, py) in enumerate(landmarks_xy):
        color = (0, 255, 0)  # default green
        radius = 6
        if deviations and i < len(deviations):
            color = get_joint_color(deviations[i])
            # Make bad joints bigger
            if deviations[i] is not None and deviations[i] > 0.18:
                radius = 10
        cv2.circle(img, (int(px), int(py)), radius, color, -1)
        cv2.circle(img, (int(px), int(py)), radius + 2, (255, 255, 255), 1)


# -------------------------
# Preset Song System
# -------------------------
# Songs are defined as lists of (key, pause_after_note) tuples
# Keys: 1 = low (C), 2 = mid (D), 3 = high (E), 
# Each tuple spawns a note with the specified key, then waits pause_after_note seconds

SONGS = {
    "mary_lamb": [
        # Mary Had a Little Lamb
        # "Ma-ry had a lit-tle lamb, lit-tle lamb, lit-tle lamb"
        (3, 1.0), (2, 1.0), (1, 1.0), (2, 1.0),  # Ma-ry had a
        (3, 1.0), (3, 1.0), (3, 1.6),           # lit-tle lamb
        (2, 1.0), (2, 1.0), (2, 1.6),           # lit-tle lamb
        (3, 1.0), (3, 1.0), (3, 1.6),           # lit-tle lamb
        # "Ma-ry had a lit-tle lamb, its fleece was white as snow"
        (3, 1.0), (2, 1.0), (1, 1.0), (2, 1.0),  # Ma-ry had a
        (3, 1.0), (3, 1.0), (3, 1.0), (3, 1.0),  # lit-tle lamb its
        (2, 1.0), (2, 1.0), (3, 1.0), (2, 1.0),  # fleece was white as
        (1, 2.0),                                # snow
    ],
    
    "hot_cross_buns": [
        # Hot Cross Buns
        # "Hot cross buns, hot cross buns"
        (3, 1.0), (2, 1.0), (1, 1.6),           # Hot cross buns
        (3, 1.0), (2, 1.0), (1, 1.6),           # hot cross buns
        # "One a pen-ny, two a pen-ny, hot cross buns"
        (1, 0.6), (1, 0.6), (1, 0.6), (1, 0.6),  # One a pen-ny (faster section)
        (2, 0.6), (2, 0.6), (2, 0.6), (2, 0.6),  # two a pen-ny (faster section)
        (3, 1.0), (2, 1.0), (1, 1.6),           # hot cross buns
    ]
}

# Song metadata for display
SONG_INFO = {
    "mary_lamb": {
        "title": "Mary Had a Little Lamb",
        "difficulty": "Easy",
        "description": "Classic nursery rhyme"
    },
    "hot_cross_buns": {
        "title": "Hot Cross Buns",
        "difficulty": "Easy",
        "description": "Traditional children's song"
    }
}

# Select which song to play (default: Mary Had a Little Lamb)
SELECTED_SONG = "mary_lamb"
song_data = SONGS[SELECTED_SONG]
song_index = 0  # Tracks current position in the song

# -------------------------
# 6. UI Helper Functions
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

def draw_miss_effect(img, x, y, age):
    """
    Draw visual miss indicator with red flash, X mark, and "MISS!" text
    Args:
        img: Image to draw on
        x, y: Position of the miss
        age: Time since miss occurred
    """
    alpha = 1 - (age / 0.8)  # Fade out over 0.8 seconds
    
    if alpha > 0:
        # Red flash/pulse
        radius = int(50 + age * 80)
        overlay = img.copy()
        cv2.circle(overlay, (int(x), int(y)), radius, (0, 0, 255), 8)
        cv2.addWeighted(overlay, alpha * 0.6, img, 1 - alpha * 0.6, 0, img)
        
        # Draw X mark
        x_size = 40
        thickness = 5
        cv2.line(img, (int(x - x_size), int(y - x_size)), 
                (int(x + x_size), int(y + x_size)), (0, 0, 255), thickness)
        cv2.line(img, (int(x + x_size), int(y - x_size)), 
                (int(x - x_size), int(y + x_size)), (0, 0, 255), thickness)
        
        # "MISS!" text
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "MISS!"
        text_size = cv2.getTextSize(text, font, 1.2, 3)[0]
        text_x = int(x - text_size[0] // 2)
        text_y = int(y - 60 - age * 30)  # Float upward
        
        # Shadow for readability
        cv2.putText(img, text, (text_x + 3, text_y + 3), font, 1.2, (0, 0, 0), 4)
        # Red text
        text_color = tuple(int(c * alpha) for c in (0, 0, 255))
        cv2.putText(img, text, (text_x, text_y), font, 1.2, text_color, 3)

def draw_incorrect_effect(img, x, y, age):
    """Draw incorrect pose visual feedback (red X and warning)"""
    alpha = 1 - (age / 0.6)  # Fade out over 0.6 seconds
    
    if alpha > 0:
        # Red pulsing circle
        radius = int(50 + age * 40)
        overlay = img.copy()
        cv2.circle(overlay, (int(x), int(y)), radius, (0, 0, 255), 5)
        cv2.addWeighted(overlay, alpha * 0.6, img, 1 - alpha * 0.6, 0, img)
        
        # Draw big red X
        x_size = 40
        x_int = int(x)
        y_int = int(y)
        color = tuple(int(c * alpha) for c in (0, 0, 255))
        
        cv2.line(img, (x_int - x_size, y_int - x_size), (x_int + x_size, y_int + x_size), color, 8)
        cv2.line(img, (x_int + x_size, y_int - x_size), (x_int - x_size, y_int + x_size), color, 8)
        
        # "WRONG!" text
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "WRONG!"
        text_size = cv2.getTextSize(text, font, 1.0, 2)[0]
        text_x = int(x - text_size[0] // 2)
        text_y = int(y + 60)
        
        cv2.putText(img, text, (text_x + 2, text_y + 2), font, 1.0, (0, 0, 0), 4)
        cv2.putText(img, text, (text_x, text_y), font, 1.0, color, 3)

# -------------------------
# 7. MediaPipe Setup
# -------------------------
# -------------------------
cap = cv2.VideoCapture(0)
frame_timestamp_ms = 0

# Initialize MediaPipe HandLandmarker globally
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, "hand_landmarker.task")
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options, running_mode=vision.RunningMode.VIDEO,
    num_hands=1, min_hand_detection_confidence=0.5
)
landmarker = vision.HandLandmarker.create_from_options(options)

# -------------------------
# 7. Flask Routes
# -------------------------
@app.route('/')
def home():
    """Home page with navigation options"""
    return render_template('home.html')

@app.route('/songs')
def song_selection():
    """Song selection screen - shows list of available songs"""
    songs = []
    for song_id, info in SONG_INFO.items():
        songs.append({
            'id': song_id,
            'title': info['title'],
            'difficulty': info['difficulty'],
            'description': info['description']
        })
    return render_template('song_selection.html', songs=songs)

@app.route('/freestyle')
def freestyle():
    """Freestyle mode - play without a specific song"""
    global freestyle_mode
    freestyle_mode = True
    session['mode'] = 'freestyle'
    return render_template('freestyle.html')

@app.route('/select_song/<song_id>')
def select_song(song_id):
    """Handle song selection and redirect to game"""
    global SELECTED_SONG, song_data, song_index, next_spawn_delay, freestyle_mode
    global score, combo, max_combo, notes, hit_effects, incorrect_effects, miss_effects
    global successful_hits, total_attempts, game_start_time, accuracy_counts
    global current_session_id, note_counter, session_joint_deviations
    global song_complete
    
    freestyle_mode = False
    session['mode'] = 'song'
    
    # Validate song exists
    if song_id in SONGS:
        SELECTED_SONG = song_id
        song_data = SONGS[song_id]
        song_index = 0
        next_spawn_delay = SPAWN_INTERVAL
        session['selected_song'] = song_id
        
        # Reset all game state so each play starts fresh
        score = 0
        combo = 0
        max_combo = 0
        notes = []
        hit_effects = []
        incorrect_effects = []
        miss_effects = []
        successful_hits = 0
        total_attempts = 0
        game_start_time = None
        accuracy_counts = {"PERFECT": 0, "GOOD": 0, "OK": 0, "MISS": 0}
        song_complete = False
        
        # Start a new DB session for rehab tracking
        note_counter = 0
        session_joint_deviations = []
        song_title = SONG_INFO.get(song_id, {}).get('title', song_id)
        current_session_id = db.create_session(song_id, song_title, mode="song")
        session['current_session_id'] = current_session_id
    
    return redirect(url_for('game'))

@app.route('/game')
def game():
    """Game screen with camera feed"""
    global freestyle_mode
    freestyle_mode = False
    session['mode'] = 'song'
    
    selected_song = session.get('selected_song', 'mary_lamb')
    song_title = SONG_INFO.get(selected_song, {}).get('title', 'Unknown Song')
    return render_template('game.html', song_title=song_title)

def generate_frames_freestyle():
    """Generator function for freestyle mode video frames"""
    global frame_timestamp_ms, last_freestyle_pose, last_audio_time, current_playing_note, history
    global last_raw_landmarks
    
    while True:
        success, image = cap.read()
        if not success: 
            break
        
        current_time = time.time()
        
        # --- HAND DETECTION ---
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = landmarker.detect_for_video(mp_image, int(frame_timestamp_ms))
        frame_timestamp_ms += 33
        
        predicted_pose_idx = None
        predicted_pose = "..."
        confidence = 0.0
        pixel_landmarks_fs = None
        
        if detection_result.hand_landmarks:
            hand = detection_result.hand_landmarks[0]
            raw = []
            for lm in hand: 
                raw.extend([lm.x, lm.y])
            
            # Build pixel-space landmarks for skeleton overlay
            img_h_fs, img_w_fs = image.shape[:2]
            pixel_landmarks_fs = [(lm.x * img_w_fs, lm.y * img_h_fs) for lm in hand]
            
            # Save normalized landmarks
            last_raw_landmarks = normalize_landmarks(raw)
            
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
        
        # --- FREESTYLE AUDIO LOGIC ---
        # Play audio continuously based on held pose
        if predicted_pose_idx is not None and predicted_pose_idx in AUDIO_NOTES:
            # If pose changed or 1 second elapsed, play the note
            if (predicted_pose_idx != last_freestyle_pose) or (current_time - last_audio_time >= 1.0):
                AUDIO_NOTES[predicted_pose_idx].play()
                last_freestyle_pose = predicted_pose_idx
                last_audio_time = current_time
                current_playing_note = predicted_pose_idx
        else:
            # No valid pose detected
            last_freestyle_pose = None
            current_playing_note = None
        
        # --- RENDER ---
        flipped = cv2.flip(image, 1)
        h, w, _ = flipped.shape
        
        # Dark overlay for better visibility
        overlay = flipped.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.1, flipped, 0.7, 0, flipped)
        
        # ── REHAB: Draw hand skeleton in freestyle mode ──
        if pixel_landmarks_fs:
            flipped_lm = [(w - px, py) for px, py in pixel_landmarks_fs]
            live_devs = None
            if predicted_pose_idx is not None and last_raw_landmarks:
                ideal = db.get_ideal_pose(predicted_pose_idx)
                if ideal:
                    live_devs = compute_joint_deviations(last_raw_landmarks, ideal["landmarks"])
            draw_hand_skeleton(flipped, flipped_lm, live_devs)
        
        # --- HUD ---
        # Freestyle Mode Label (top center)
        mode_text = "FREESTYLE MODE"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(mode_text, font, 1.2, 3)[0]
        text_x = w // 2 - text_size[0] // 2
        cv2.putText(flipped, mode_text, (text_x + 3, 53), font, 1.2, (0, 0, 0), 5)
        cv2.putText(flipped, mode_text, (text_x, 50), font, 1.2, (255, 100, 255), 3)
        
        # Current pose detection (center)
        if predicted_pose_idx is not None:
            pose_display = f"{predicted_pose.upper()}"
            
            # Get note name (palm=F, fist=G)
            note_names = {0: "F", 1: "C", 2: "D", 3: "E", 4: "G"}
            note_name = note_names.get(predicted_pose_idx, "")
            
            if note_name:
                pose_display += f" ({note_name})"
            
            pose_size = cv2.getTextSize(pose_display, font, 2.0, 4)[0]
            pose_x = w // 2 - pose_size[0] // 2
            pose_y = h // 2
            
            # Glow effect if playing
            if current_playing_note == predicted_pose_idx:
                cv2.putText(flipped, pose_display, (pose_x + 4, pose_y + 4), font, 2.0, (0, 0, 0), 8)
                cv2.putText(flipped, pose_display, (pose_x, pose_y), font, 2.0, (100, 255, 255), 4)
            else:
                cv2.putText(flipped, pose_display, (pose_x + 3, pose_y + 3), font, 2.0, (0, 0, 0), 6)
                cv2.putText(flipped, pose_display, (pose_x, pose_y), font, 2.0, (200, 200, 200), 3)
        
        # Confidence bar (bottom)
        conf_w = 300
        conf_x = w // 2 - conf_w // 2
        conf_y = h - 40
        cv2.rectangle(flipped, (conf_x, conf_y), (conf_x + conf_w, conf_y + 20), (50, 50, 50), -1)
        if confidence > 0:
            cv2.rectangle(flipped, (conf_x, conf_y), (conf_x + int(conf_w * confidence), conf_y + 20), 
                         (100, 255, 100), -1)
        cv2.putText(flipped, f"Confidence: {int(confidence * 100)}%", (conf_x + conf_w + 10, conf_y + 15), 
                   font, 0.5, (255, 255, 255), 1)
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', flipped)
        frame = buffer.tobytes()
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def generate_frames():
    """Generator function for video frames"""
    global frame_timestamp_ms, game_start_time, last_spawn, notes, score, combo, max_combo
    global hit_effects, incorrect_effects, miss_effects, history, song_index, next_spawn_delay
    global successful_hits, total_attempts, accuracy_counts, HIT_ZONE_Y
    global current_session_id, note_counter, last_raw_landmarks, session_joint_deviations
    global song_complete
    
    while True:
        success, image = cap.read()
        if not success: 
            break
        
        current_time = time.time()
        
        # Dynamically set HIT_ZONE_Y based on actual camera frame height.
        # Place the hit zone at ~72% of the frame so notes have room to
        # fall past it and trigger the miss detection (which needs +80 px).
        frame_h = image.shape[0]
        HIT_ZONE_Y = int(frame_h * 0.72)
        
        # Initialize game timer
        if game_start_time is None:
            game_start_time = current_time
            last_spawn = current_time
        
        game_time = current_time - game_start_time
        
        # --- SPAWN NEW NOTES (Song-Based) ---
        # Check if enough time has passed AND there are more notes in the song
        if song_index < len(song_data) and current_time - last_spawn > next_spawn_delay:
            # Get the next note from the song
            key, pause_after = song_data[song_index]
            
            # Map key to pose index (key 1->pose "1", key 2->pose "2", key 3->pose "3")
            # poses = ["palm", "1", "2", "3", "fist"]
            # So key 1 = pose index 1, key 2 = pose index 2, key 3 = pose index 3
            pose_idx = key
            
            h, w, _ = image.shape
            lane_x = w - LANE_WIDTH  # Right side lane
            
            # Spawn the note
            note = Note(pose_idx, current_time, lane_x, HIT_ZONE_Y, NOTE_SPEED)
            notes.append(note)
            
            # Update spawn timing and song position
            last_spawn = current_time
            next_spawn_delay = pause_after  # Set the pause duration for the next note
            song_index += 1  # Move to next note in song
        
        # If all notes have been spawned AND all on-screen notes are resolved,
        # the song is truly finished — finalize and stop.
        if song_index >= len(song_data) and len(notes) == 0 and not song_complete:
            # ── REHAB: Finalize session when song completes ──
            if current_session_id:
                acc_pct = (successful_hits / total_attempts * 100) if total_attempts > 0 else 0
                # Compute average joint deviations across all notes
                avg_devs = None
                if session_joint_deviations:
                    avg_devs = [0.0] * 21
                    counts = [0] * 21
                    for devs in session_joint_deviations:
                        for i, d in enumerate(devs):
                            if d is not None:
                                avg_devs[i] += d
                                counts[i] += 1
                    avg_devs = [round(avg_devs[i] / counts[i], 4) if counts[i] > 0 else None for i in range(21)]
                db.end_session(
                    current_session_id, score, max_combo, total_attempts,
                    successful_hits, accuracy_counts["MISS"],
                    accuracy_counts["PERFECT"], accuracy_counts["GOOD"], accuracy_counts["OK"],
                    round(acc_pct, 1), avg_devs
                )
            
            song_complete = True  # Signal the frontend to redirect
        
        # --- HAND DETECTION ---
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = landmarker.detect_for_video(mp_image, int(frame_timestamp_ms))
        frame_timestamp_ms += 33
        
        predicted_pose_idx = None
        predicted_pose = "..."
        confidence = 0.0
        raw_landmarks_42 = None       # Raw 42-element flat list for this frame
        pixel_landmarks = None        # 21 (px, py) tuples for skeleton drawing
        
        if detection_result.hand_landmarks:
            hand = detection_result.hand_landmarks[0]
            raw = []
            for lm in hand: 
                raw.extend([lm.x, lm.y])
            raw_landmarks_42 = raw  # Save for joint tracking
            
            # Build pixel-space landmark list for skeleton overlay
            img_h_det, img_w_det = image.shape[:2]
            pixel_landmarks = [(lm.x * img_w_det, lm.y * img_h_det) for lm in hand]
            
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
            
            # Save normalized landmarks for rehab tracking
            if raw_landmarks_42:
                last_raw_landmarks = normalize_landmarks(raw_landmarks_42)
        
        # --- UPDATE NOTES ---
        # Get image dimensions for cleanup bounds
        img_h = image.shape[0]
        active_notes = []
        
        for note in notes:
            note.update(current_time)
            
            # ──────────────────────────────────────────────────
            # AUDIO + INCORRECT FEEDBACK
            # When a note enters the hit zone, play the user's
            # detected pose audio.  If the pose is wrong, show
            # an incorrect visual indicator.
            # ──────────────────────────────────────────────────
            if not note.hit and not note.missed and note.is_in_hit_zone():
                # Play audio based on user's detected pose (once per note)
                if not note.audio_played and predicted_pose_idx is not None:
                    if predicted_pose_idx in AUDIO_NOTES:
                        AUDIO_NOTES[predicted_pose_idx].play()
                    note.audio_played = True
                
                # Show incorrect visual feedback if wrong pose
                if predicted_pose_idx is not None and predicted_pose_idx != note.pose_idx:
                    if not note.incorrect_shown:
                        incorrect_effects.append({
                            'x': note.lane_x,
                            'y': note.current_y,
                            'time': current_time
                        })
                        note.incorrect_shown = True
            
            # ──────────────────────────────────────────────────
            # STEP 1 — HIT CHECK (correct pose while in zone)
            # Must run BEFORE miss check so a last-frame hit is
            # not accidentally counted as a miss.
            # ──────────────────────────────────────────────────
            if not note.hit and not note.missed and note.is_in_hit_zone():
                if predicted_pose_idx == note.pose_idx:
                    accuracy = note.get_hit_accuracy()
                    note.hit = True
                    note.hit_time = current_time

                    # HIT: increment BOTH successful_hits and total_attempts
                    successful_hits += 1
                    total_attempts += 1

                    score += {"PERFECT": 100, "GOOD": 75, "OK": 50}.get(accuracy, 0)
                    combo += 1
                    max_combo = max(max_combo, combo)
                    accuracy_counts[accuracy] += 1

                    # Visual pop for the hit
                    hit_effects.append({
                        'x': note.lane_x,
                        'y': note.current_y,
                        'accuracy': accuracy,
                        'time': current_time,
                    })

                    # ── REHAB: Record per-joint data for this HIT ──
                    if current_session_id and last_raw_landmarks:
                        ideal = db.get_ideal_pose(note.pose_idx)
                        ideal_lm = ideal["landmarks"] if ideal else None
                        devs = compute_joint_deviations(last_raw_landmarks, ideal_lm) if ideal_lm else None
                        if devs:
                            session_joint_deviations.append(devs)
                        db.add_note_data(
                            session_id=current_session_id,
                            note_index=note_counter,
                            pose_expected=note.pose_idx,
                            pose_detected=predicted_pose_idx,
                            accuracy_label=accuracy,
                            hit=True,
                            landmarks_detected=last_raw_landmarks,
                            landmarks_ideal=ideal_lm,
                            joint_deviations=devs,
                            timestamp=current_time,
                        )
                        note_counter += 1

            # ──────────────────────────────────────────────────
            # STEP 2 — MISS CHECK (note fell past the hit zone)
            # A note is missed when it drops 80 px below the hit
            # zone without being hit.  We set note.missed = True
            # so this block only fires ONCE per note.
            # ──────────────────────────────────────────────────
            if not note.hit and not note.missed and note.has_passed_hit_zone():
                note.missed = True          # flag so we never re-enter

                # MISS: reset combo to 0  (combo text hides automatically)
                combo = 0

                # MISS: only total_attempts goes up — successful_hits stays
                total_attempts += 1
                accuracy_counts["MISS"] += 1

                # MISS: visual feedback — red flash / X / "MISS!" text
                miss_effects.append({
                    'x': note.lane_x,
                    'y': HIT_ZONE_Y,
                    'time': current_time,
                })

                # ── REHAB: Record per-joint data for this MISS ──
                if current_session_id:
                    ideal = db.get_ideal_pose(note.pose_idx)
                    ideal_lm = ideal["landmarks"] if ideal else None
                    devs = compute_joint_deviations(last_raw_landmarks, ideal_lm) if (last_raw_landmarks and ideal_lm) else None
                    if devs:
                        session_joint_deviations.append(devs)
                    db.add_note_data(
                        session_id=current_session_id,
                        note_index=note_counter,
                        pose_expected=note.pose_idx,
                        pose_detected=predicted_pose_idx,
                        accuracy_label="MISS",
                        hit=False,
                        landmarks_detected=last_raw_landmarks,
                        landmarks_ideal=ideal_lm,
                        joint_deviations=devs,
                        timestamp=current_time,
                    )
                    note_counter += 1

            # ──────────────────────────────────────────────────
            # STEP 3 — KEEP / REMOVE the note from the list
            # • Hit notes stay briefly for the pop animation
            # • Missed notes are dropped immediately (their
            #   miss_effects entry handles the visual)
            # • Other notes stay while they are on-screen
            # ──────────────────────────────────────────────────
            keep = False
            if note.hit:
                # Show hit animation for 0.5 s then remove
                if current_time - note.hit_time < 0.5:
                    keep = True
            elif note.missed:
                # Already registered — remove from active list
                keep = False
            else:
                # Note is still falling — keep while on-screen
                if note.current_y < img_h + 100:
                    keep = True

            if keep:
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
        
        # ── REHAB: Draw hand skeleton overlay with joint deviation colors ──
        if pixel_landmarks:
            # Mirror the pixel landmarks to match the flipped image
            flipped_landmarks = [(w - px, py) for px, py in pixel_landmarks]
            # Compute live deviations if we have ideal pose data
            live_devs = None
            if predicted_pose_idx is not None and last_raw_landmarks:
                ideal = db.get_ideal_pose(predicted_pose_idx)
                if ideal:
                    live_devs = compute_joint_deviations(last_raw_landmarks, ideal["landmarks"])
            draw_hand_skeleton(flipped, flipped_landmarks, live_devs)
        
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
        
        # Draw miss effects (red flash, X, "MISS!" text)
        miss_effects = [e for e in miss_effects if current_time - e['time'] < 0.8]
        for effect in miss_effects:
            age = current_time - effect['time']
            draw_miss_effect(flipped, effect['x'], effect['y'], age)
        
        # Draw incorrect pose effects
        incorrect_effects = [e for e in incorrect_effects if current_time - e['time'] < 0.6]
        for effect in incorrect_effects:
            age = current_time - effect['time']
            draw_incorrect_effect(flipped, effect['x'], effect['y'], age)
        
        # Draw combo (only show if combo > 1, hidden on miss until new combo starts)
        if combo > 1:
            draw_combo(flipped, combo, w - LANE_WIDTH, 100)
        
        # --- HUD ---
        # Score panel (top left) - expanded to include accuracy
        cv2.rectangle(flipped, (10, 10), (250, 150), (40, 40, 40), -1)
        cv2.rectangle(flipped, (10, 10), (250, 150), (100, 100, 100), 3)
        
        cv2.putText(flipped, f"SCORE: {score}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(flipped, f"MAX COMBO: {max_combo}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # Calculate and display live accuracy
        if total_attempts > 0:
            accuracy_percent = (successful_hits / total_attempts) * 100
            accuracy_color = (100, 255, 100) if accuracy_percent >= 80 else (255, 255, 100) if accuracy_percent >= 60 else (100, 100, 255)
            cv2.putText(flipped, f"ACCURACY: {accuracy_percent:.1f}%", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, accuracy_color, 2)
        else:
            cv2.putText(flipped, f"ACCURACY: ---%", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        cv2.putText(flipped, f"TIME: {int(game_time)}s", (20, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
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
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', flipped)
        frame = buffer.tobytes()
        
        # Yield frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """Video streaming route - redirects to appropriate feed based on mode"""
    mode = session.get('mode', 'song')
    if mode == 'freestyle':
        return Response(generate_frames_freestyle(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return Response(generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

# ──────────────────────────────────────────────────
# REHAB API ROUTES
# ──────────────────────────────────────────────────

@app.route('/calibrate')
def calibrate():
    """Calibration page to capture ideal poses for each of the 5 gestures."""
    existing = db.get_all_ideal_poses()
    captured = {p["pose_idx"]: True for p in existing}
    pose_list = [
        {"idx": i, "name": poses[i], "captured": captured.get(i, False)}
        for i in range(5)
    ]
    return render_template('calibrate.html', poses=pose_list)


def generate_calibration_frames():
    """Video feed for calibration — shows hand skeleton + detected pose."""
    global frame_timestamp_ms, last_raw_landmarks, history
    
    while True:
        success, image = cap.read()
        if not success:
            break

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = landmarker.detect_for_video(mp_image, int(frame_timestamp_ms))
        frame_timestamp_ms += 33

        predicted_pose_idx = None
        predicted_pose = "..."
        confidence = 0.0
        pixel_lm = None

        if detection_result.hand_landmarks:
            hand = detection_result.hand_landmarks[0]
            raw = []
            for lm in hand:
                raw.extend([lm.x, lm.y])
            
            img_h_c, img_w_c = image.shape[:2]
            pixel_lm = [(lm.x * img_w_c, lm.y * img_h_c) for lm in hand]
            last_raw_landmarks = normalize_landmarks(raw)

            wrist_x, wrist_y = raw[0], raw[1]
            nx = [raw[i] - wrist_x for i in range(0, 42, 2)]
            ny = [raw[i] - wrist_y for i in range(1, 42, 2)]
            combined = nx + ny
            max_val = max(abs(max(combined)), abs(min(combined)))

            if max_val > 0:
                input_data = torch.tensor([[v / max_val for v in combined]], dtype=torch.float32)
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

        flipped = cv2.flip(image, 1)
        h, w, _ = flipped.shape

        # Dark overlay
        overlay = flipped.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.15, flipped, 0.85, 0, flipped)

        # Skeleton
        if pixel_lm:
            flipped_lm = [(w - px, py) for px, py in pixel_lm]
            draw_hand_skeleton(flipped, flipped_lm)

        # HUD
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(flipped, "CALIBRATION", (20, 40), font, 1.0, (255, 200, 100), 2)
        if predicted_pose_idx is not None:
            cv2.putText(flipped, f"Detected: {predicted_pose.upper()} ({int(confidence*100)}%)",
                        (20, 80), font, 0.8, (100, 255, 100), 2)
        else:
            cv2.putText(flipped, "Show your hand...", (20, 80), font, 0.8, (200, 200, 200), 1)

        ret, buffer = cv2.imencode('.jpg', flipped)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/calibrate_feed')
def calibrate_feed():
    """Video feed for calibration page."""
    return Response(generate_calibration_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/capture_pose', methods=['POST'])
def api_capture_pose():
    """Capture current hand landmarks as the ideal for a given pose index."""
    global last_raw_landmarks
    data = request.get_json()
    pose_idx = data.get("pose_idx")
    
    if pose_idx is None or pose_idx not in range(5):
        return jsonify({"error": "Invalid pose_idx"}), 400
    
    if not last_raw_landmarks:
        return jsonify({"error": "No hand detected. Show your hand to the camera."}), 400
    
    db.save_ideal_pose(pose_idx, poses[pose_idx], last_raw_landmarks)
    return jsonify({"success": True, "pose": poses[pose_idx]})


@app.route('/api/song_status')
def api_song_status():
    """Polled by game.html to know when the song is finished."""
    return jsonify({
        "complete": song_complete,
        "session_id": session.get('current_session_id'),
    })


@app.route('/api/sessions')
def api_sessions():
    """Get all sessions, optionally filtered by song_id."""
    song_id = request.args.get('song_id')
    limit = request.args.get('limit', 50, type=int)
    sessions = db.get_all_sessions(limit=limit, song_id=song_id)
    return jsonify(sessions)


@app.route('/api/session/<int:session_id>')
def api_session(session_id):
    """Get a single session's details."""
    s = db.get_session(session_id)
    if not s:
        return jsonify({"error": "Session not found"}), 404
    # Parse avg_joint_deviations
    if s.get("avg_joint_deviations"):
        s["avg_joint_deviations"] = json.loads(s["avg_joint_deviations"])
    return jsonify(s)


@app.route('/api/session/<int:session_id>/notes')
def api_session_notes(session_id):
    """Get per-note data for a session."""
    notes_data = db.get_session_notes(session_id)
    return jsonify(notes_data)


@app.route('/api/session/<int:session_id>/joints')
def api_session_joints(session_id):
    """Get per-joint average deviations for a session."""
    avgs = db.get_joint_averages(session_id)
    if not avgs:
        return jsonify({"error": "No joint data"}), 404
    result = [{"index": i, "name": db.LANDMARK_NAMES[i], "avg_deviation": avgs[i]} for i in range(21)]
    return jsonify(result)


@app.route('/api/compare')
def api_compare():
    """Compare two sessions' joint data. ?a=<id>&b=<id>"""
    a = request.args.get('a', type=int)
    b = request.args.get('b', type=int)
    if not a or not b:
        return jsonify({"error": "Provide ?a=<session_id>&b=<session_id>"}), 400
    comparison = db.get_session_comparison(a, b)
    if not comparison:
        return jsonify({"error": "No data for one or both sessions"}), 404
    return jsonify(comparison)


@app.route('/api/progress')
def api_progress():
    """Get accuracy trend over recent sessions."""
    song_id = request.args.get('song_id')
    limit = request.args.get('limit', 20, type=int)
    data = db.get_progress_over_time(song_id=song_id, limit=limit)
    return jsonify(data)


@app.route('/api/ideal_poses')
def api_ideal_poses():
    """Check which ideal poses have been captured."""
    all_poses = db.get_all_ideal_poses()
    captured = {p["pose_idx"]: True for p in all_poses}
    return jsonify({
        "has_all": db.has_ideal_poses(),
        "poses": [{"idx": i, "name": poses[i], "captured": captured.get(i, False)} for i in range(5)]
    })


@app.route('/results')
def results():
    """Session results page (redirected after song completion)."""
    sid = request.args.get('session_id') or session.get('current_session_id')
    if not sid:
        return redirect(url_for('dashboard'))
    s = db.get_session(int(sid))
    if not s:
        return redirect(url_for('dashboard'))
    # Parse JSON field
    if s.get("avg_joint_deviations") and isinstance(s["avg_joint_deviations"], str):
        s["avg_joint_deviations"] = json.loads(s["avg_joint_deviations"])
    joints = db.get_joint_averages(int(sid))
    joint_data = []
    if joints:
        joint_data = [{"index": i, "name": db.LANDMARK_NAMES[i], "avg_deviation": joints[i]} for i in range(21)]
    return render_template('results.html', session=s, joint_data=joint_data, landmark_names=db.LANDMARK_NAMES)


@app.route('/export/<int:session_id>')
def export_csv(session_id):
    """Export session data as CSV."""
    s = db.get_session(session_id)
    if not s:
        return "Session not found", 404
    notes_data = db.get_session_notes(session_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Session ID", session_id, "Song", s["song_title"], "Accuracy", s["accuracy"]])
    writer.writerow([])
    
    # Per-note header
    header = ["Note#", "Expected Pose", "Detected Pose", "Accuracy", "Hit"]
    for name in db.LANDMARK_NAMES:
        header.append(f"{name}_deviation")
    writer.writerow(header)
    
    # Per-note data
    for note in notes_data:
        row = [
            note["note_index"],
            poses[note["pose_expected"]] if note["pose_expected"] is not None else "",
            poses[note["pose_detected"]] if note["pose_detected"] is not None else "",
            note["accuracy_label"],
            "HIT" if note["hit"] else "MISS",
        ]
        devs = note.get("joint_deviations", [])
        if devs:
            for d in devs:
                row.append(round(d, 5) if d is not None else "")
        else:
            row.extend([""] * 21)
        writer.writerow(row)
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"}
    )


@app.route('/dashboard')
def dashboard():
    """Dashboard - view stats and progress"""
    sessions = db.get_all_sessions(limit=50)
    has_calibration = db.has_ideal_poses()
    return render_template('dashboard.html', sessions=sessions, has_calibration=has_calibration,
                           songs=SONG_INFO, landmark_names=db.LANDMARK_NAMES)

# -------------------------
# 8. Main Entry Point
# -------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)