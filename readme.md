# ✨ Codify ✨

**Your AI-Powered Coding Co-pilot: See, Speak, Code, Conquer!**

Codify isn't just another editor; it's an intelligent development environment supercharged by Google Gemini. It sees your screen, understands your project, talks to you, executes commands, manages your Git workflow, and helps you write better code, faster.

[![Codify Interface Mockup](https://codify-ai.netlify.app/api.png)](https://codify-ai.netlify.app)

---

## Try: https://codify-ai.netlify.app

## 🚀 Core Features

*   **🧠 AI-Powered Code Analysis & Generation:**
    *   Leverage Gemini to analyze your codebase based on natural language prompts.
    *   Get intelligent suggestions, find bugs, and generate new code snippets or entire files.
    *   Receive structured JSON output for seamless automated refactoring or file modifications.
*   **🚀 Super Agent Mode – The Ultimate AI Assistant:**
    *   Just give instructions, and Codify takes full control of the development process—writing, executing, and updating code until the target is achieved! 
    *   It even provides real-time updates by talking back and interacting with your screen view, it auto-saves changes without human intervention.
*   **👁️ Live Screen Understanding (Vision Mode):**
    *   Let Codify "watch" your screen (e.g., a running application, a terminal with errors).
    *   Provide a prompt (e.g., "Why is my app crashing?", "What's on the screen?"), and Gemini will analyze the visual context.
    *   Get real-time summaries and insights, with an option for Codify to tell you when its "vision" task is complete.
*   **💬 Interactive AI Chat & Voice Interaction:**
    *   Talk directly to Gemini! Ask questions, brainstorm ideas, or get explanations.
    *   Codify provides voice feedback for screen analysis and chat, making interaction hands-free and natural.
*   **🔧 Integrated Terminal & Command Execution:**
    *   Run shell commands (Python, pip, npm, node, git, etc.) directly within Codify.
    *   Stream real-time output from your commands.
    *   Stop long-running processes and even send input to interactive commands.
*   **📝 Smart Code Autocompletion:**
    *   Get substantial, context-aware code completions powered by Gemini, helping you write code faster and with fewer errors.
*   **📂 Full Project File Management:**
    *   Easily browse, open, read, and write files within your project directory.
    *   Quickly find files using patterns.
*   **🌿 Git Version Control Interface:**
    *   Initialize Git repositories.
    *   Stage changes, commit, and push to remotes.
    *   View commit history (for the project and individual files).
    *   Create and checkout branches.
    *   Set up remote repositories.
*   **💻 Desktop App Experience:**
    *   Runs as a local desktop application using `pywebview` for a native feel, powered by a Flask backend.

---

## 🛠️ Tech Stack

*   **Backend:** Python, Flask, Flask-SocketIO
*   **AI:** Google Generative AI (Gemini Pro, Gemini Flash)
*   **Desktop UI:** `pywebview`
*   **Screen Capture:** `mss`, `OpenCV`
*   **Voice:** `pyttsx3`
*   **Version Control:** `pygit2`, `subprocess` for Git CLI
*   **Environment:** `python-dotenv`

---

## 🏁 Getting Started

### Prerequisites

*   Python 3.8+
*   `pip` (Python package installer)
*   Git

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AyushmanTomar/codify.git
    cd codify
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    Create a `requirements.txt` file with the following content:
    ```txt
    Flask
    Flask-SocketIO
    google-generativeai
    python-dotenv
    pywebview
    opencv-python
    mss
    numpy
    pyttsx3
    pygit2
    ```
    Then run:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up API Key:**
    *   Create a `.env` file in the root of the project.
    *   Add your Google Gemini API key:
        ```env
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        # Optional: Set a default project directory
        # DEFAULT_PROJECT_DIR="/path/to/your/projects/codify_workspace"
        ```
    *   You can get a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

5.  **Run the application:**
     `python app.py `

### First Launch

1.  On the first launch, if the Gemini API key isn't found in the environment, Codify might prompt you to enter it in the UI.
2.  You might be asked for a unique key for a simple login. (mail to: ayushmantomar721@gmail.com)
3.  Set your project path through the UI if it's not the default `~/codify`.

---

## 🎮 How to Use

*   **Project Path:** Set your working project directory via the UI. This is where Codify will manage files and run commands.
*   **API Key:** Enter your own API key to use Codify.
*   **Code Editor:** Write and modify your code. Use `Tab` for AI autocompletion.
*   **AI Analysis (Chat):**
    *   Select files you want the AI to consider.
    *   Type your request in the main chat/prompt input (e.g., "Refactor this Python code to be more efficient," "Explain this function," "Write a test case for this.").
    *   Codify will provide a summary, suggested changes (with diffs), and necessary commands.
*   **Vision Mode:**
    *   Click the "Start Screen Analysis" button.
    *   Codify will stream your screen to Gemini and give you spoken and text feedback.
    *   Click "Stop Screen Analysis" when done.
*   **Terminal:**
    *   Type commands in the terminal input (e.g., `python my_script.py`, `pip install <package>`).
    *   View real-time output. For long-running server commands, you'll see an option to stop them.
*   **Git Integration:**
    *   Access Git features through the dedicated "Git" tab or section.
    *   View status, stage files, commit, push, manage branches, and view history.
*   **Talk Live:**
    *   Use the "Talk Live" feature to have a spoken conversation with the AI.

---

## 📂 Project Structure (Key Files)

*   `your_main_script_name.py`: Main application file (Flask backend, Socket.IO, `webview` integration, API routes).
*   `screen_analyzer.py`: Class responsible for screen capture, Gemini vision analysis, and voice feedback logic.
*   `templates/`: Contains HTML templates for the web UI.
    *   `index.html`: Main application interface.
    *   `login.html`: Simple key-based login page.
    *   `gitmain.html`: Git interface page.
    *   `setup.html`, `error.html`, `setup_remote.html`, `file_history.html`: Other Git-related UI pages.
*   `static/`: (Likely contains CSS, JavaScript, images for the frontend - not provided but implied by Flask structure).
*   `.env`: For storing API keys and environment variables (you need to create this).
*   `requirements.txt`: Lists Python dependencies (you need to create this).


---

Happy Coding with Codify! 🚀