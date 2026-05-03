from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import cv2
import mediapipe as mp
import numpy as np
import os
import requests
import json
from datetime import datetime

from database import SessionLocal, User, WorkoutSession, WorkoutSet

app = FastAPI()

# Serve static files (Chart.js bundle)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- 1. BIOMECHANICS ENGINE (MediaPipe) ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

def calculate_angle(a, b, c):
    a = np.array(a) # First
    b = np.array(b) # Mid
    c = np.array(c) # End
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    if angle > 180.0:
        angle = 360 - angle
        
    return angle

# --- GLOBAL STATE & TELEMETRY ---
counter = 0 
stage = None
telemetry_data = {"reps": 0, "state": "IDLE"}

# --- CENTROID LOCK VARIABLES ---
anchor_centroid = None  # Stores the (x, y) of the primary user
LOCK_RADIUS = 0.25      # 25% of the screen width - The "Safety Bubble"

# --- DATABASE SESSION TRACKING ---
current_session_id = None  # Set when a plan is generated
current_user_name = None   # Set when a plan is generated
current_exercise = "Bicep Curls"  # Active exercise for FSM joint selection

# --- CAMERA RESOURCE MANAGEMENT ---
active_cap = None  # Track the active VideoCapture to prevent resource leaks

def generate_frames():
    global counter, stage, telemetry_data, anchor_centroid, active_cap
    
    # Reset anchor for fresh lock on each camera session
    anchor_centroid = None
    
    # Release any previous camera capture to prevent freeze
    if active_cap is not None:
        active_cap.release()
        import time
        time.sleep(0.5)
        print("[SYSTEM] Released previous camera capture.")
    
    print("[SYSTEM] Initializing integrated webcam...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    active_cap = cap
    
    if not cap.isOpened():
        print("[FATAL ERROR] Could not open webcam.")
        return
    
    try:
        # Warm-up: discard first few frames while the sensor stabilizes
        for _ in range(5):
            cap.read()
    
        print("[SUCCESS] Webcam feed acquired. Starting 3s countdown...")
        
        # --- 3-SECOND COUNTDOWN before centroid lock ---
        import time
        countdown_duration = 3
        countdown_start = time.time()
        
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            elapsed = time.time() - countdown_start
            remaining = countdown_duration - elapsed
            
            if remaining <= 0:
                print("[SYSTEM] Countdown complete. Centroid lock armed.")
                break
            
            # Draw countdown overlay on the frame
            h, w = frame.shape[:2]
            # Dark overlay
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)
            
            # Countdown number
            count_text = str(int(remaining) + 1)
            text_size = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_SIMPLEX, 5, 8)[0]
            text_x = (w - text_size[0]) // 2
            text_y = (h + text_size[1]) // 2
            cv2.putText(frame, count_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 5, (0, 229, 255), 8, cv2.LINE_AA)
            
            # Instruction text
            cv2.putText(frame, "GET IN POSITION", (w//2 - 180, text_y + 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            
            # Stream the countdown frame
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        print("[SYSTEM] Starting pose detection.")
            
        with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while True:
                success, frame = cap.read()
                if not success:
                    break
    
                # Recolor image to RGB for MediaPipe
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                
                # Make detection
                results = pose.process(image)
            
                # Recolor back to BGR for OpenCV rendering
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                
                try:
                    landmarks = results.pose_landmarks.landmark
                    
                    # 1. Extract Arm Coordinates — BOTH ARMS for Bicep Curls
                    l_shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                    l_elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                    l_wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
                    r_shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
                    r_elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
                    r_wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
                    
                    # 2. Extract Torso Coordinates (For the Centroid Lock)
                    l_sh = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                    r_sh = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                    l_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
                    r_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
                    
                    # 3. Calculate Current Center of Mass (Average X and Y)
                    current_cx = (l_sh.x + r_sh.x + l_hip.x + r_hip.x) / 4.0
                    current_cy = (l_sh.y + r_sh.y + l_hip.y + r_hip.y) / 4.0
                    
                    # 4. INITIALIZE THE ANCHOR (only if full torso is visible)
                    if anchor_centroid is None:
                        torso_visible = all(v > 0.6 for v in [l_sh.visibility, r_sh.visibility, l_hip.visibility, r_hip.visibility])
                        if torso_visible:
                            anchor_centroid = (current_cx, current_cy)
                            print(f"SYSTEM LOCKED ONTO PRIMARY USER AT: {anchor_centroid}")
                        else:
                            # Show waiting message until full torso is detected
                            cv2.putText(image, 'WAITING FOR FULL BODY...', (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 229, 255), 2, cv2.LINE_AA)
                    
                    # 5. CALCULATE DISTANCE (skip if anchor not yet set)
                    if anchor_centroid is None:
                        raise Exception("Waiting for lock")
                    
                    dx = current_cx - anchor_centroid[0]
                    dy = current_cy - anchor_centroid[1]
                    
                    # For Squats, heavily discount vertical (Y) displacement since the user goes down
                    if current_exercise == "Squats":
                        distance = abs(dx)
                    else:
                        distance = np.sqrt(dx**2 + dy**2)
                    
                    # 6. THE BIOMECHANICAL GATEKEEPER
                    if distance <= LOCK_RADIUS:
                        # Draw targeting box
                        cv2.circle(image, (int(current_cx * 640), int(current_cy * 480)), 10, (0, 255, 0), -1)
                        cv2.putText(image, "LOCKED", (int(current_cx * 640) - 30, int(current_cy * 480) - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        # --- EXERCISE-AWARE FSM ---
                        if current_exercise == "Squats":
                            # Track Hip -> Knee -> Ankle (both legs, averaged)
                            l_hip_pt = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x, landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
                            l_knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
                            l_ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
                            r_hip_pt = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
                            r_knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
                            r_ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]
                            
                            l_vis = min(landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].visibility, landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].visibility, landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].visibility)
                            r_vis = min(landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].visibility, landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].visibility, landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].visibility)
                            
                            angle_down = 90; angle_up = 170
                            lost_msg = '[!] TARGET LOST: ALIGN LEGS'
                            
                            # Use both legs if visible, else best visible
                            if l_vis > 0.5 and r_vis > 0.5:
                                angle = (calculate_angle(l_hip_pt, l_knee, l_ankle) + calculate_angle(r_hip_pt, r_knee, r_ankle)) / 2
                                display_joint = l_knee
                                vis_ok = True
                            elif l_vis > 0.5:
                                angle = calculate_angle(l_hip_pt, l_knee, l_ankle)
                                display_joint = l_knee
                                vis_ok = True
                            elif r_vis > 0.5:
                                angle = calculate_angle(r_hip_pt, r_knee, r_ankle)
                                display_joint = r_knee
                                vis_ok = True
                            else:
                                vis_ok = False
                        else:
                            # Bicep Curls — BOTH ARMS tracked
                            l_vis = min(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].visibility, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].visibility, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].visibility)
                            r_vis = min(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].visibility, landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].visibility, landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].visibility)
                            
                            angle_down = 30; angle_up = 160
                            lost_msg = '[!] TARGET LOST: ALIGN ARMS'
                            
                            # Use both arms if visible, else best visible
                            if l_vis > 0.5 and r_vis > 0.5:
                                angle = (calculate_angle(l_shoulder, l_elbow, l_wrist) + calculate_angle(r_shoulder, r_elbow, r_wrist)) / 2
                                display_joint = l_elbow
                                vis_ok = True
                            elif l_vis > 0.5:
                                angle = calculate_angle(l_shoulder, l_elbow, l_wrist)
                                display_joint = l_elbow
                                vis_ok = True
                            elif r_vis > 0.5:
                                angle = calculate_angle(r_shoulder, r_elbow, r_wrist)
                                display_joint = r_elbow
                                vis_ok = True
                            else:
                                vis_ok = False
                        
                        if vis_ok:
                            # Dynamic Progress Bar
                            per = np.interp(angle, (angle_down, angle_up), (100, 0))
                            bar_val = np.interp(angle, (angle_down, angle_up), (100, 380))
                            
                            cv2.rectangle(image, (580, 100), (610, 380), (255, 255, 0), 2)
                            cv2.rectangle(image, (580, int(bar_val)), (610, 380), (255, 255, 0), cv2.FILLED)
                            cv2.putText(image, f"{int(angle)} DEG", tuple(np.multiply(display_joint, [640, 480]).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
                            
                            # Exercise label
                            cv2.putText(image, current_exercise.upper(), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 229, 255), 2, cv2.LINE_AA)
                            
                            # FSM Logic
                            if angle > angle_up:
                                stage = "ECCENTRIC" 
                            if angle < angle_down and stage == "ECCENTRIC":
                                stage = "CONCENTRIC"
                                counter += 1
                                
                            telemetry_data["reps"] = counter
                            telemetry_data["state"] = stage if stage else "IDLE"
                            telemetry_data["exercise"] = current_exercise
                        else:
                            cv2.putText(image, lost_msg, (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    else:
                        # INTRUDER DETECTED
                        cv2.putText(image, '[!] INTRUDER DETECTED - TRACKING PAUSED', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
                        cv2.circle(image, (int(current_cx * 640), int(current_cy * 480)), 10, (0, 0, 255), -1)
                        
                except Exception as e:
                    pass
                
                # --- Neon Skeletal Overlay ---
                if results.pose_landmarks:
                    mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                            mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=2, circle_radius=2),
                                            mp_drawing.DrawingSpec(color=(255, 0, 255), thickness=2, circle_radius=2))
                
                # --- CRITICAL MISSING YIELD LOGIC ---
                # This is what actually sends the image to your HTML frontend
                ret, buffer = cv2.imencode('.jpg', image)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        cap.release()
        active_cap = None
        print("[SYSTEM] Camera released.")

# --- 2. FASTAPI ENDPOINTS ---

def preview_frames():
    global active_cap
    if active_cap is not None:
        active_cap.release()
        import time
        time.sleep(0.5)
        
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    active_cap = cap
    if not cap.isOpened():
        return
        
    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
                
            # Add preview overlay
            cv2.putText(frame, "PREVIEW MODE - POSITION YOURSELF", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 229, 255), 2, cv2.LINE_AA)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally:
        cap.release()
        active_cap = None

@app.get("/preview_feed")
def preview_feed():
    return StreamingResponse(preview_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
# --- 2. FASTAPI ENDPOINTS ---

@app.get("/")
def home():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/telemetry")
def get_telemetry():
    return telemetry_data
