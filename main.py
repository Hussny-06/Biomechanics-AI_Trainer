import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

# VARIABLES
counter = 0 
stage = None 
feedback = "Stand in Frame"

# LAYOUT CONSTANTS
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
SIDEBAR_WIDTH = 300 # Width of the analytics panel

def calculate_angle(a, b, c):
    """ Calculates angle between three joints """
    a = np.array(a) 
    b = np.array(b) 
    c = np.array(c) 
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    if angle > 180.0:
        angle = 360-angle
        
    return angle

# Setup Camera
cap = cv2.VideoCapture(0)

# Setup Window to be resizable
cv2.namedWindow('Biomechanical Analytics Pro', cv2.WINDOW_NORMAL)

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 1. Create the Master Canvas (Black Background)
        # shape is (Height, Width, Color Channels)
        canvas = np.zeros((WINDOW_HEIGHT, WINDOW_WIDTH, 3), dtype=np.uint8)
        
        # 2. Process Camera Feed
        # Resize webcam frame to fit the RIGHT side of the canvas
        feed_width = WINDOW_WIDTH - SIDEBAR_WIDTH
        resized_frame = cv2.resize(frame, (feed_width, WINDOW_HEIGHT))
        
        # Color Conversion for MediaPipe
        image = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # 3. Logic & Processing
        try:
            landmarks = results.pose_landmarks.landmark
            
            # Get Keypoints
            sh_point = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            el_point = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            wr_point = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]

            # Visibility Check
            if (sh_point.visibility > 0.5 and el_point.visibility > 0.5 and wr_point.visibility > 0.5):
                
                shoulder = [sh_point.x, sh_point.y]
                elbow = [el_point.x, el_point.y]
                wrist = [wr_point.x, wr_point.y]
                
                angle = calculate_angle(shoulder, elbow, wrist)

                # VISUALIZATION: Angle on Body
                # We need to map coordinates to the resized frame size
                elbow_pixel = tuple(np.multiply(elbow, [feed_width, WINDOW_HEIGHT]).astype(int))
                
                cv2.putText(image, str(int(angle)), elbow_pixel, 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(image, str(int(angle)), elbow_pixel, 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
                
                # Analytics Calculation
                per = np.interp(angle, (30, 160), (100, 0))
                # Bar height maps to the Sidebar height (padding included)
                bar = np.interp(angle, (30, 160), (100, WINDOW_HEIGHT - 100))
                
                bar_color = (0, 255, 0) if per >= 90 else (0, 255, 255)
                
                # Logic
                if angle > 160:
                    stage = "down"
                    feedback = " UP"
                if angle < 30 and stage =='down':
                    stage = "up"
                    counter += 1
                    feedback = " GOOD"
            else:
                per = 0
                bar = WINDOW_HEIGHT - 100
                bar_color = (100, 100, 100)
                feedback = "Step Back"

            # Draw Landmarks on the Video Feed
            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                mp_drawing.DrawingSpec(color=(255,255,255), thickness=2, circle_radius=2), 
                                mp_drawing.DrawingSpec(color=(0,255,0), thickness=2, circle_radius=2))

        except:
            pass

        # 4. COMPOSE THE CANVAS
        
        # A. Fill Sidebar (Left: 0 to 300) with Dark Gray
        canvas[:, :SIDEBAR_WIDTH] = (30, 30, 30) 
        
        # B. Place Video Feed (Right: 300 to End)
        canvas[:, SIDEBAR_WIDTH:] = image

        # 5. DRAW UI ELEMENTS (On the Sidebar Region)
        
        # Title
        cv2.putText(canvas, "AI TRAINER", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        # Rep Counter
        cv2.putText(canvas, str(int(counter)), (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 3.5, (255, 255, 255), 4)
        cv2.putText(canvas, "REPS", (25, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        # Power Bar Background
        # Coordinates are relative to the whole canvas, so x is between 0-300
        cv2.rectangle(canvas, (180, 100), (220, WINDOW_HEIGHT - 100), (50, 50, 50), -1)
        # Active Bar
        cv2.rectangle(canvas, (180, int(bar)), (220, WINDOW_HEIGHT - 100), bar_color, -1)
        # Percentage
        cv2.putText(canvas, f'{int(per)}%', (175, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # Feedback/Stage Box
        cv2.rectangle(canvas, (20, 300), (150, 400), (60, 60, 60), -1) # Box background
        cv2.putText(canvas, "STATE", (30, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(canvas, stage if stage else "--", (30, 370), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        
        # Feedback Message (Bottom)
        cv2.putText(canvas, feedback, (20, WINDOW_HEIGHT - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0) if feedback=="Step Back" else (255, 255, 255), 2)
        if feedback == "Step Back":
             # Draw a red warning box if user is out of frame
             cv2.rectangle(canvas, (0, WINDOW_HEIGHT-80), (300, WINDOW_HEIGHT), (0, 0, 255), -1)
             cv2.putText(canvas, "STEP BACK", (40, WINDOW_HEIGHT - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)


        # 6. Show the Master Canvas
        cv2.imshow('Biomechanical Analytics Pro', canvas)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()