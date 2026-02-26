from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import cv2
import mediapipe as mp
import numpy as np
import threading

app = FastAPI()

# --- YOUR EXISTING AI LOGIC ---
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Global Variables for State
class State:
    def __init__(self):
        self.counter = 0
        self.stage = None
        self.feedback = "Stand in Frame"

state = State()

def calculate_angle(a, b, c):
    a = np.array(a) 
    b = np.array(b) 
    c = np.array(c) 
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    if angle > 180.0: angle = 360-angle
    return angle

def generate_frames():
    cap = cv2.VideoCapture(0)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        
        # 1. Resize for performance
        frame = cv2.resize(frame, (1024, 768))
        
        # 2. Process AI
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        try:
            landmarks = results.pose_landmarks.landmark
            sh_point = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            el_point = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            wr_point = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]

            if (sh_point.visibility > 0.5 and el_point.visibility > 0.5 and wr_point.visibility > 0.5):
                shoulder = [sh_point.x, sh_point.y]
                elbow = [el_point.x, el_point.y]
                wrist = [wr_point.x, wr_point.y]
                
                angle = calculate_angle(shoulder, elbow, wrist)
                
                # Update Logic
                if angle > 160:
                    state.stage = "down"
                    state.feedback = "UP"
                if angle < 30 and state.stage =='down':
                    state.stage = "up"
                    state.counter += 1
                    state.feedback = "GOOD"
                
                # Draw Visuals (Server Side Rendering for now)
                cv2.putText(image, str(int(angle)), tuple(np.multiply(elbow, [1024, 768]).astype(int)), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            else:
                state.feedback = "Step Back"

            # Draw Skeleton
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
        except:
            pass
        
        # 3. Encode Frame to JPEG (for Browser)
        ret, buffer = cv2.imencode('.jpg', image)
        frame = buffer.tobytes()
        
        # Yield frame in a standard HTTP Multipart stream
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.get("/")
def home():
    # Simple HTML Client embedded in Python
    html_content = """
    <html>
        <head>
            <title>AI Gym Trainer - Web Client</title>
            <style>
                body { background-color: #1a1a1a; color: white; font-family: sans-serif; text-align: center; }
                h1 { margin-top: 20px; }
                .container { display: flex; justify-content: center; margin-top: 20px; }
                img { border: 5px solid #00ff00; border-radius: 10px; }
                .stats { margin-top: 20px; font-size: 24px; }
            </style>
        </head>
        <body>
            <h1>AI Biomechanics Engine (FastAPI Stream)</h1>
            <div class="container">
                <img src="/video_feed" width="800">
            </div>
            <div class="stats">
                Status: <b>Live Inference Running</b>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# To run: uvicorn server:app --reload