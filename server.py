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
                
                # 2. Get Visibility (Confidence Scores from 0.0 to 1.0)
                shoulder_vis = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].visibility
                elbow_vis = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].visibility
                wrist_vis = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].visibility
                
                # 3. THE CONFIDENCE GATEKEEPER
                # Only calculate math if the AI is >50% sure it sees the arm
                if shoulder_vis > 0.5 and elbow_vis > 0.5 and wrist_vis > 0.5:
                    angle = calculate_angle(shoulder, elbow, wrist)
                    
                    cv2.putText(image, str(int(angle)), 
                                   tuple(np.multiply(elbow, [640, 480]).astype(int)), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
                    
                    # Finite State Machine Logic
                    if angle > 160:
                        stage = "down"
                    if angle < 30 and stage =='down':
                        stage="up"
                        counter +=1
                else:
                    # Warning if user steps out of frame
                    cv2.putText(image, 'ALIGN FULL ARM IN FRAME', (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2, cv2.LINE_AA)
                    
            except:
                pass
            
            cv2.rectangle(image, (0,0), (225,73), (245,117,16), -1)
            cv2.putText(image, 'REPS', (15,12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1, cv2.LINE_AA)
            cv2.putText(image, str(counter), (10,60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255,255,255), 2, cv2.LINE_AA)
            cv2.putText(image, 'STAGE', (65,12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1, cv2.LINE_AA)
            cv2.putText(image, stage, (60,60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255,255,255), 2, cv2.LINE_AA)
            
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                    mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2), 
                                    mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2))
            
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