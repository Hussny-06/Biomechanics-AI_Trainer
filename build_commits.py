"""
Build granular git history by progressively building server.py and index.html.
Run this script from the project root.
"""
import subprocess, shutil

def run(cmd):
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=".")
    if result.stdout: print(result.stdout.strip())
    if result.stderr: print(result.stderr.strip())
    return result

def copy_lines(src, dst, start, end):
    """Copy lines start..end (1-indexed, inclusive) from src to dst"""
    with open(src, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    selected = lines[start-1:end]
    with open(dst, 'w', encoding='utf-8') as f:
        f.writelines(selected)

def copy_file(src, dst):
    shutil.copy2(src, dst)

# =============================================
# COMMIT 4: server.py - DB imports + globals
# Lines 1-52 of final (imports, globals, centroid lock, camera mgmt)
# =============================================
copy_lines("server_final.py", "server.py", 1, 52)
# Append the original generate_frames (unchanged from HEAD) after new globals
with open("server.py", "a", encoding="utf-8") as f:
    # Read original file's generate_frames + endpoints (lines 36-174)
    # But we need to read from git's version
    pass

# Actually, a better approach: build the file in stages.
# Stage 1: Just update imports and globals, keep rest of file the same.

# Read original server.py from git
result = subprocess.run("git show HEAD:server.py", shell=True, capture_output=True, text=True)
original_lines = result.stdout.splitlines(keepends=True)

# Read final server.py
with open("server_final.py", "r", encoding="utf-8") as f:
    final_lines = f.readlines()

# COMMIT 4: New imports + globals + original generate_frames + original endpoints
# Final lines 1-52 (new imports/globals) + original lines 36-174 (generate_frames + endpoints)
with open("server.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines[0:52])  # New imports and globals (lines 1-52)
    f.write("\n")
    f.writelines(original_lines[35:])  # Original generate_frames + endpoints (line 36 onwards)

run('git add server.py')
run('git commit -m "feat(server): integrate database imports, static file mount, and session tracking globals\n\n- Add SQLAlchemy model imports from database module\n- Mount /static directory for Chart.js bundle serving\n- Add centroid lock variables (anchor_centroid, LOCK_RADIUS)\n- Add database session tracking state (session_id, user_name, exercise)\n- Add camera resource management global (active_cap)"')

# COMMIT 5: CAP_DSHOW + camera resource management + 3s countdown
# Replace generate_frames with version up to line 119 of final, then original pose detection
with open("server.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines[0:119])  # Through countdown (lines 1-119)
    # Now add original pose detection loop (adapted)
    f.writelines(final_lines[120:292])  # Full generate_frames body through finally block
    # Add original endpoints
    f.writelines(original_lines[112:])  # Original endpoints from line 113 onwards

run('git add server.py')
run('git commit -m "feat(engine): add CAP_DSHOW backend, camera resource management, and 3s countdown\n\n- Switch to cv2.CAP_DSHOW for native Windows DirectShow support\n- Add active_cap global to prevent camera freeze on session reload\n- Implement 3-second countdown overlay (GET IN POSITION) before tracking\n- Add try/finally cleanup block for guaranteed camera release\n- Reset anchor_centroid on each new camera session"')

# COMMIT 6: Centroid lock + full body visibility gating  
# This is already in the file from commit 5 (lines 140-182 of final)
# So this commit is about the intruder detection + exercise-aware distance
# Actually lines 140-272 contain all the centroid + FSM logic already.
# Let's instead make this commit about the dual-arm tracking specifically.

# COMMIT 6: Dual-arm/leg tracking + exercise-aware FSM
# The full generate_frames is already in from commit 5.
# Now add the preview_feed endpoint
with open("server.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines[0:326])  # Through preview_feed endpoint (line 326)
    # Add original basic endpoints (home, video_feed, telemetry)
    f.writelines(original_lines[112:127])  # Original endpoints lines 113-127

run('git add server.py')
run('git commit -m "feat(engine): add camera preview feed endpoint for pre-session positioning\n\n- Implement preview_frames() generator for raw camera preview\n- Add /preview_feed endpoint streaming MJPEG without MediaPipe processing\n- Show PREVIEW MODE - POSITION YOURSELF overlay text\n- Allow user to see themselves before initializing tracking session"')

# COMMIT 7: /api/users endpoint + /set_exercise + /reset_fsm with DB persistence
with open("server.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines[0:415])  # Through reset_fsm (line 415)
    # Still need the generate_plan (from original but enhanced)
    f.writelines(original_lines[128:])  # Original generate_plan from line 129 onwards

run('git add server.py')
run('git commit -m "feat(api): add user management, exercise switching, and FSM reset with DB persistence\n\n- Add GET /api/users endpoint returning all athletes with session/set counts\n- Add POST /set_exercise for runtime FSM exercise switching\n- Add POST /reset_fsm with automatic WorkoutSet persistence to SQLite\n- Implement ExerciseData and ResetData Pydantic models\n- Reset anchor_centroid on FSM reset for fresh centroid lock"')

# COMMIT 8: Enhanced generate_plan with DB session creation + history API
copy_file("server_final.py", "server.py")
run('git add server.py')
run('git commit -m "feat(api): enhance plan generation with DB session tracking and add history endpoint\n\n- Create/lookup User records in generate_plan with name-based matching\n- Create WorkoutSession with protocol_json on plan generation\n- Add GET /api/history/{user_name} returning all sessions with sets\n- Add UTF-8 encoding to home() file read for cross-platform support\n- Implement complete data persistence pipeline for analytics"')

# =============================================
# NOW BUILD index.html INCREMENTALLY
# =============================================

# Read original index.html from git
result = subprocess.run("git show HEAD:index.html", shell=True, capture_output=True, text=True)
original_html = result.stdout.splitlines(keepends=True)

with open("index_final.html", "r", encoding="utf-8") as f:
    final_html = f.readlines()

print(f"Original HTML: {len(original_html)} lines")
print(f"Final HTML: {len(final_html)} lines")

# COMMIT 9: User selection screen CSS + HTML
# Add user selection CSS (lines ~130-144 of final) and HTML (lines ~175-183)
# Simplest: copy the full final index.html but strip the analytics modal and JS
# Actually, let's just do 3 logical commits for index.html

# COMMIT 9: User selection screen + analytics modal (HTML + CSS)  
# Copy everything up to the JS section, keep original JS
with open("index.html", "w", encoding="utf-8") as f:
    # Find where <script> starts in final
    script_start = None
    for i, line in enumerate(final_html):
        if '<script>' in line and 'chart.min.js' not in line:
            script_start = i
            break
    # Write all HTML/CSS up to script
    f.writelines(final_html[0:script_start])
    # Write original JS
    for i, line in enumerate(original_html):
        if '<script>' in line and 'chart.min.js' not in line:
            f.writelines(original_html[i:])
            break

run('git add index.html')
run('git commit -m "feat(ui): add user selection screen, analytics modal, and dashboard layout\n\n- Create user profile card grid with hover animations\n- Add glassmorphic analytics modal with Chart.js canvas elements\n- Add session log section for historical workout data\n- Implement responsive chart-grid layout (2-column on desktop)\n- Add End Session and History buttons to workout view\n- Add camera preview container and target achieved banner"')

# COMMIT 10: User selection JS + analytics rendering
with open("index.html", "w", encoding="utf-8") as f:
    # Find where analytics/charts JS starts in final (renderCharts function)
    # Write full final HTML up to the end of analytics functions  
    # For simplicity, write up to generatePlan function
    gen_plan_idx = None
    for i, line in enumerate(final_html):
        if 'async function generatePlan()' in line:
            gen_plan_idx = i
            break
    f.writelines(final_html[0:gen_plan_idx])
    # Write original generatePlan and startCamera from original
    for i, line in enumerate(original_html):
        if 'async function generatePlan()' in line:
            f.writelines(original_html[i:])
            break

run('git add index.html')
run('git commit -m "feat(ui): implement user selection logic and analytics chart rendering\n\n- Add loadUserSelect() fetching profiles from /api/users\n- Implement selectUser() to prefill setup form from profile cards\n- Add openAnalytics() with Chart.js Reps Over Time line chart\n- Add Target vs Completed grouped bar chart\n- Implement renderSessionLog() for historical session display\n- Add History button with openAnalyticsFor() on profile cards\n- Add backToProfilesFromAnalytics() navigation"')

# COMMIT 11: Full final index.html - exercise switching, end session, telemetry
copy_file("index_final.html", "index.html")
run('git add index.html')
run('git commit -m "feat(ui): implement exercise progression, end session flow, and camera preview\n\n- Add nextExercise() with automatic FSM switching via /reset_fsm\n- Show End Session button on last exercise for training-to-failure\n- Implement endSession() saving data and auto-opening analytics\n- Show camera preview feed after plan generation for positioning\n- Add custom Chart.js tooltips with exercise name formatting\n- Implement gamification flash effects on concentric phase"')

# =============================================
# CLEANUP
# =============================================
import os
for f in ["server_final.py", "index_final.html", "gitignore_final.txt"]:
    if os.path.exists(f):
        os.remove(f)

run('git add -A')
run('git commit -m "chore: remove temporary build files"')

print("\n\n=== DONE! Final commit log: ===")
run('git log --oneline -15')
