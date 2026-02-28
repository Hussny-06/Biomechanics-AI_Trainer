# AI Biomechanics Engine & Workout Planner 🚀

An edge-computing web application that tracks human biomechanics in real-time using Computer Vision, validates repetitions using a deterministic Finite State Machine, and generates personalized workout protocols using a locally hosted Large Language Model (Llama 3).

## 🛠️ Architecture Overview

* **Core Language:** Python 3.11
* **Frontend:** Vanilla HTML/CSS/JS (Single Page Application)
* **Backend:** FastAPI (Python) serving asynchronous HTTP streams
* **Vision Engine:** OpenCV + Google MediaPipe (BlazePose)
* **AI Generative Layer:** Meta Llama 3 running locally via Ollama

---

## ⚙️ Local Setup & Installation

To run this project on your local machine, follow these steps exactly.

### Step 1: Clone & Setup Python Environment

Ensure you have **Python 3.11** installed. Open your terminal and run:

```bash
# Clone the repo
git clone <YOUR-GITHUB-REPO-LINK-HERE>
cd Biomechanics_MiniProject_SemVI

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.\.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install all project dependencies
pip install -r requirements.txt
```

### Step 2: Install the AI Engine (Ollama)

The AI engine runs completely locally. Follow the steps for your specific Operating System:

**For Windows:**
*Note: Due to Windows 11 Smart App Control, we run the AI engine via Linux (WSL) for maximum stability.*

1. Open PowerShell as Administrator and run: `wsl --install`
2. Restart your PC if prompted, open the **Ubuntu** app from your Start Menu, and run:
   `curl -fsSL https://ollama.com/install.sh | sh`

**For macOS:**

1. Download Ollama directly from the official website: [ollama.com/download](https://ollama.com/download)
2. Unzip and drag the Ollama app to your Applications folder, then open it.
*(Alternatively, if you use Homebrew, you can simply run: `brew install ollama` in your terminal).*

**For Linux:**

1. Open your terminal and run: `curl -fsSL https://ollama.com/install.sh | sh`

### Step 3: Download the AI Brain

Regardless of your operating system, once Ollama is installed, open your terminal (the Ubuntu terminal for Windows users, or the standard terminal for Mac/Linux users) and run:

```bash
ollama run llama3
```

*Wait for the 4.7 GB model to download. Once you see the `>>>` prompt, type `/bye` and hit Enter. The AI engine is now silently running in the background on port `11434`.*

---

## 🚀 Running the Application

Once your dependencies are installed and the Ollama instance is running, start the application server:

1. Ensure your Python virtual environment `(.venv)` is active in your terminal.
2. Boot the FastAPI server:

   ```bash
   uvicorn server:app --reload --port 8080
   ```

3. Open your web browser and navigate to:
   **`http://localhost:8080`**

### Usage Instructions

1. Fill out the Athlete Protocol form and click **Generate AI Plan**. The Python backend will securely contact the local AI engine to generate your routine.
2. Click **Initialize Camera Feed**.
3. Step back so the camera clearly sees your shoulder, elbow, and wrist. The system's **Confidence Gatekeeper** will not begin tracking until it confirms full visibility of the required joints.
