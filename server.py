from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
import cv2
import mediapipe as mp
import numpy as np
import os
import requests
import json

app = FastAPI()

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

counter = 0 
stage = None

# --- GLOBAL TELEMETRY STATE ---
telemetry_data = {"reps": 0, "state": "IDLE"}

def generate_frames():
    global counter, stage
    cap = cv2.VideoCapture(0)
    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            try:
                landmarks = results.pose_landmarks.landmark
                
                # 1. Get Coordinates
                shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
                
                # 2. Get Visibility Confidence
                shoulder_vis = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].visibility
                elbow_vis = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].visibility
                wrist_vis = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].visibility
                
                # 3. THE CONFIDENCE GATEKEEPER
                if shoulder_vis > 0.5 and elbow_vis > 0.5 and wrist_vis > 0.5:
                    angle = calculate_angle(shoulder, elbow, wrist)
                    
                    # --- HUD ELEMENT 1: Dynamic Progress Bar ---
                    # Map the angle (160 down to 30 up) to a percentage (0% to 100%)
                    per = np.interp(angle, (30, 160), (100, 0))
                    # Map the percentage to a pixel height for the bar (e.g., 380px to 100px)
                    bar_val = np.interp(angle, (30, 160), (100, 380))
                    
                    # Draw the empty bar border
                    cv2.rectangle(image, (580, 100), (610, 380), (255, 255, 0), 2)
                    # Fill the bar based on the angle (Neon Cyan)
                    cv2.rectangle(image, (580, int(bar_val)), (610, 380), (255, 255, 0), cv2.FILLED)
                    
                    # --- HUD ELEMENT 2: Floating Angle Text ---
                    cv2.putText(image, f"{int(angle)} DEG", 
                               tuple(np.multiply(elbow, [640, 480]).astype(int)), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
                    
                   # Finite State Machine Logic
                    global telemetry_data
                    if angle > 160:
                        stage = "ECCENTRIC" 
                    if angle < 30 and stage == "ECCENTRIC":
                        stage = "CONCENTRIC"
                        counter += 1
                        
                    # Feed the bridge
                    telemetry_data["reps"] = counter
                    telemetry_data["state"] = stage if stage else "IDLE"
                else:
                    # Warning if user steps out of frame
                    cv2.putText(image, '[!] TARGET LOST: ALIGN ARM', (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    
            except:
                pass
            
          
            # --- HUD ELEMENT 4: Neon Skeletal Overlay ---
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                    mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=2, circle_radius=2),   # Joints (Cyan)
                                    mp_drawing.DrawingSpec(color=(255, 0, 255), thickness=2, circle_radius=2))  # Connections (Magenta)
            
            ret, buffer = cv2.imencode('.jpg', image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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

# --- 3. THE GENERATIVE AI LAYER (Ollama Bridge) ---

class UserProfile(BaseModel):
    name: str
    goal: str
    level: str

@app.post("/api/generate_plan")
def generate_plan(profile: UserProfile):
    prompt = f"""
    You are an expert AI fitness coach. Create a workout plan for {profile.name}, a {profile.level} whose goal is {profile.goal}. 
    Return ONLY a valid JSON object with a 'routine' array. 
    We currently only support two exercises: 'Bicep Curls' and 'Squats'.
    Calculate scientifically accurate rep targets based on their level and goal.
    Format exactly like this:
    {{
        "routine": [
            {{"exercise": "Bicep Curls", "reps": 12}},
            {{"exercise": "Squats", "reps": 15}}
        ]
    }}
    """
    
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False,
        "format": "json" # Forces clean JSON output
    }
    
    try:
        # Talks to WSL Linux on port 11434
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        data = response.json()
        ai_json = json.loads(data["response"])
        return ai_json
        
    except Exception as e:
        print(f"Ollama Error: {e}")
        # Fallback if Linux isn't running
        return {
            "routine": [
                {"exercise": "Bicep Curls", "reps": 10},
                {"exercise": "Squats", "reps": 10}
            ]
        }