from flask import Flask, render_template, request, jsonify, session, redirect, url_for,Response
import os
import threading
import json
import google.generativeai as genai
import time
import re
from dotenv import load_dotenv
import glob
import logging
import webview
import sys
import subprocess
import signal
from threading import Event
from flask_socketio import SocketIO
from screen_analyzer import ScreenAnalyzer
import pyttsx3
from datetime import datetime
import pygit2

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app and Socket.IO without eventlet
app = Flask(__name__)
app.secret_key = "4f3c5e5c6a4b2f9a6d8e7f1a3c5b4d9f"
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# Default project directory
DEFAULT_PROJECT_DIR = os.getenv("DEFAULT_PROJECT_DIR", os.path.join(os.path.expanduser("~"), "projects"))

# Global variables
model = None
active_processes = {}  # Store running processes
command_stop_events = {}  # Events to signal stopping a command
analyzer = None
chat = None

def initialize_gemini():
    """Initialize Gemini API with API key from environment variables"""
    global model,analyzer

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            analyzer = ScreenAnalyzer(GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25') #gemini-2.0-flash-lite
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Error configuring Gemini API: {e}")
            model = None
    else:
        logger.warning("No Gemini API key found in environment variables")
        model = None

# Define routes
@app.route('/autocomplete', methods=['POST'])
def autocomplete():
    global model
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    data = request.get_json()
    exist_code = data['code']

    prompt = f"""You are an AI code completion assistant. Given a code snippet, your task is to predict the most likely and complete continuation of the code. Aim to provide a substantial code block, such as a function definition or a logical code segment, that seamlessly integrates with the existing code.

    Programming Language: Detect by seeing the existing code

    Existing Code:
    ```
    {exist_code}
    ```

    Instructions:

    1.  **Provide Substantial Code Completion:**  Instead of just completing the current line, generate a meaningful block of code that expands upon the existing code. This could be a function, a class, a loop, or a conditional block – whatever logically fits the context.
    2.  **Understand Context:** Deeply analyze the existing code to understand its purpose, data structures, variables, and intended functionality.
    3.  **Seamless Integration:** The generated code MUST be syntactically correct, logically consistent, and seamlessly integrated with the existing code.  It should feel like a natural extension written by the same developer.
    4.  **Completeness:** Ensure all code blocks (functions, loops, conditionals) are properly opened and closed.
    5.  **Correctness:**  Prioritize correctness. The generated code should compile or run without errors, where applicable.
    6.  **Adhere to Language Conventions:** Strictly adhere to the syntax and coding style conventions of the specified programming language.
    7.  **Avoid Repetition:** Do not simply repeat existing code. Focus on *extending* the code in a useful and predictable way.
    8.  **No Extraneous Text:**  Return only the generated code, without any introductory or explanatory text.

    Output Format:

    *   Return *only* the suggested code completion. Do not include any surrounding text, code block delimiters, or explanations.
    *   Use "\\n" for newlines. Maintain correct indentation and syntax for the given language.
    *   Use "\\t" for python formating

    Example:

    Existing Code:
    ```
    function calculateArea(width, height) {{
      return width * height;
    }}

    function calculateCircumference(radius) {{
      return 2 * Math.PI *
    ```

    Output:
    ```
    radius;\\n}}
    ```

    Now, generate the code completion for the given existing code in detected language.
    """

    generation_config = {"max_output_tokens": 8000}
    response = model.generate_content(prompt, generation_config=generation_config)
    model = genai.GenerativeModel('gemini-2.5-pro-exp-03-25')

    return jsonify({"completion": response.text.strip()})
    



# Define routes
@app.route('/start_stream', methods=['POST'])
def start_stream():
    print("in start stream function")
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({'error': 'Missing prompt in request'}), 400
    if(not analyzer):
        return jsonify({"message": "No API Key"}), 400
    success, message = analyzer.start_stream(data['prompt'])
    status_code = 200 if success else 429 if "wait" in message else 400
    return jsonify({"status": "success" if success else "error", "message": message}), status_code
    
@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    success, message = analyzer.stop_stream()
    return jsonify({"status": "success" if success else "error", "message": message})
    
@app.route('/stream')
def stream():
    def generate():
        while analyzer.is_streaming():
            frame_data = analyzer.get_encoded_frame()
            if frame_data:
                yield f"data:image/jpeg;base64,{frame_data}\n\n"
            time.sleep(analyzer.get_frame_interval())
            
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    
@app.route('/get_gemini_response')
def get_gemini_response():
    response_data = {"response": analyzer.get_response()}
    return jsonify(response_data)


@app.route('/api/set-api-key', methods=['POST'])
def set_api_key():
    """Set the Gemini API key"""
    global model,analyzer

    data = request.json
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({
            "success": False,
            "message": "No API key provided"
        }), 400

    try:
        # Configure Gemini with the new API key
        genai.configure(api_key=api_key)
        analyzer = ScreenAnalyzer(api_key)
        # Test the configuration by creating a model
        test_model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')

        # If successful, save the API key securely
        session['gemini_api_key'] = api_key

        # Update the global model
        model = test_model

        logger.info("Gemini API key configured successfully")

        return jsonify({
            "success": True,
            "message": "API key saved and verified"
        })
    except Exception as e:
        logger.error(f"Error configuring Gemini API: {e}")
        return jsonify({
            "success": False,
            "message": f"Error configuring Gemini API: {str(e)}"
        }), 400

@app.route('/api/shutdown', methods=['POST'])
def shutdown_api():
    """Shutdown the Flask server"""
    try:
        logger.info("Server shutdown requested")
        # Stop all running processes before shutting down
        stop_all_processes()
        # Use PyWebView's method to destroy the window
        webview.windows[0].destroy()
        return jsonify({"success": True, "message": "Server shutting down..."})
    except Exception as e:
        logger.error(f"Error shutting down server: {e}")
        os._exit(0)

# Also add a route for /shutdown for convenience
@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown_alt():
    """Alternative shutdown endpoint for convenience"""
    return shutdown_api()

@app.route('/api/check-api-key', methods=['GET'])
def check_api_key():
    """Check if Gemini API key is configured"""
    api_key = session.get('gemini_api_key') or os.getenv("GEMINI_API_KEY")

    return jsonify({
        "success": True,
        "is_configured": bool(api_key)
    })

@app.before_request
def load_api_key():
    """Load API key from session before each request"""
    global model,analyzer

    if model is None and 'gemini_api_key' in session:
        api_key = session['gemini_api_key']
        try:
            genai.configure(api_key=api_key)
            analyzer = ScreenAnalyzer(api_key)
            model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')
            logger.info("Gemini API configured from session")
        except Exception as e:
            logger.error(f"Error configuring Gemini API from session: {e}")

@app.route('/')
def index():
    if 'logged_in' in session and session['logged_in']:
        """Render the main application page"""
        return render_template('index.html')
    else:
        return redirect(url_for('uniq_key'))

def speak_message(message):
    """
    Speaks a message immediately in the background without using the queue system.
    
    Args:
        message (str): The message to be spoken
    """
    if not message:
        return
        
    # Create a separate thread for speaking this specific message
    speak_thread = threading.Thread(target=speak_single_message, args=(message,))
    speak_thread.daemon = True
    speak_thread.start()

def speak_single_message(message):
    """
    Internal helper method to speak a single message without queue dependencies.
    
    Args:
        message (str): The message to be spoken
    """
    try:
        time.sleep(1)
        # Create a new speech engine instance for this message
        speech_engine = pyttsx3.init()
        # Set voice properties
        speech_engine.setProperty('rate', 200)  # Faster speech
        speech_engine.setProperty('volume', 1.0)  # Full volume
        
        print(f"Direct speaking at {time.strftime('%H:%M:%S')}: {message}")
        speech_engine.say(message)
        speech_engine.runAndWait()
        print(f"Finished direct speaking at {time.strftime('%H:%M:%S')}")
        speech_engine.stop()
    except Exception as e:
        print(f"Direct speech error: {e}")


@app.route('/speak', methods=['POST'])
def speak():
    try:
        data = request.json
        msg = data.get('message_to_speak')
        
        if not msg:
            return jsonify({
                'status': 'error',
                'message': 'No text provided to speak'
            }), 400
        
        # Speak the message
        speak_message(msg)
        
        # Return success response
        return jsonify({
            'status': 'success',
            'message': 'Text is being spoken',
            'text': msg
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error processing speak request: {str(e)}'
        }), 500



@app.route('/key_uniq')
def uniq_key():
    return render_template('login.html')




@app.route('/set_key_uniq',methods=['POST'])
def set_uniq_key():
    data = request.json
    key = data.get('uniq_key')
    if key == 'abc':
        session['logged_in']=True
    else:
        session['logged_in']=False
    return redirect(url_for('index'))

@app.route('/api/set-project-path', methods=['POST'])
def set_project_path():
    """Set the current project path in the session"""
    data = request.json
    project_path = data.get('path', DEFAULT_PROJECT_DIR)

    if not os.path.exists(project_path):
        return jsonify({
            "success": False,
            "message": f"Path does not exist: {project_path}"
        }), 400

    session['project_path'] = project_path
    logger.info(f"Project path set to: {project_path}")

    return jsonify({
        "success": True,
        "message": f"Project path set to: {project_path}"
    })

@app.route('/api/list-files', methods=['GET'])
def list_files():
    """List files in the current project directory"""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)

    if not os.path.exists(project_path):
        return jsonify({
            "success": False,
            "message": f"Project path does not exist: {project_path}"
        }), 400

    try:
        files = []
        for root, _, filenames in os.walk(project_path):
            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), project_path)
                if filename.startswith('.') or rel_path.startswith('.') or "Lib" in rel_path or "Scripts" in rel_path:
                    continue

                # rel_path = os.path.relpath(os.path.join(root, filename), project_path)
                files.append(rel_path)

        return jsonify({
            "success": True,
            "files": files
        })
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({
            "success": False,
            "message": f"Error listing files: {str(e)}"
        }), 500

@app.route('/api/read-file', methods=['POST'])
def read_file():
    """Read a file from the project directory"""
    data = request.json
    file_path = data.get('path')

    if not file_path:
        return jsonify({
            "success": False,
            "message": "No file path provided"
        }), 400

    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    full_path = os.path.join(project_path, file_path)

    # Check path traversal attack
    if not os.path.normpath(full_path).startswith(os.path.normpath(project_path)):
        return jsonify({
            "success": False,
            "message": "Invalid file path"
        }), 400

    if not os.path.exists(full_path):
        return jsonify({
            "success": False,
            "message": f"File does not exist: {file_path}"
        }), 404

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            "success": True,
            "content": content,
            "path": file_path
        })
    except Exception as e:
        logger.error(f"Error reading file {full_path}: {e}")
        return jsonify({
            "success": False,
            "message": f"Error reading file: {str(e)}"
        }), 500

@app.route('/api/write-file', methods=['POST'])
def write_file():
    """Write content to a file in the project directory"""
    data = request.json
    file_path = data.get('path')
    content = data.get('content')

    if not file_path or content is None:
        return jsonify({
            "success": False,
            "message": "File path or content missing"
        }), 400

    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    full_path = os.path.join(project_path, file_path)

    # Check path traversal attack
    if not os.path.normpath(full_path).startswith(os.path.normpath(project_path)):
        return jsonify({
            "success": False,
            "message": "Invalid file path"
        }), 400

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({
            "success": True,
            "message": f"File {file_path} written successfully"
        })
    except Exception as e:
        logger.error(f"Error writing to file {full_path}: {e}")
        return jsonify({
            "success": False,
            "message": f"Error writing to file: {str(e)}"
        }), 500

@app.route('/api/find-files', methods=['POST'])
def find_files():
    """Find files matching a pattern in the project directory"""
    data = request.json
    pattern = data.get('pattern', '*.*')

    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)

    try:
        # Find files matching the pattern
        matching_files = []
        for root, _, _ in os.walk(project_path):
            for file_path in glob.glob(os.path.join(root, pattern)):
                if os.path.isfile(file_path):
                    rel_path = os.path.relpath(file_path, project_path)
                    matching_files.append(rel_path)

        return jsonify({
            "success": True,
            "files": matching_files
        })
    except Exception as e:
        logger.error(f"Error finding files: {e}")
        return jsonify({
            "success": False,
            "message": f"Error finding files: {str(e)}"
        }), 500

def make_non_blocking(pipe):
    """Make a pipe non-blocking"""
    if pipe is None:
        return
        
    if os.name == 'nt':  # Windows
        import msvcrt
        try:
            msvcrt.setmode(pipe.fileno(), os.O_BINARY)
        except (ImportError, ValueError, OSError) as e:
            logger.error(f"Error setting binary mode: {e}")
    else:  # Unix/Linux
        import fcntl
        try:
            fd = pipe.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        except (ValueError, OSError) as e:
            logger.error(f"Error setting non-blocking mode: {e}")

def read_non_blocking(pipe, chunk_size=4096):
    """Read from a non-blocking pipe"""
    if pipe is None:
        return b""
        
    try:
        return os.read(pipe.fileno(), chunk_size)
    except (BlockingIOError, ValueError, OSError):
        return b""  # No data available or pipe closed

def stream_output(process, command_id, stop_event):
    """Stream the output of a process to connected clients"""
    # Send initial message
    socketio.emit('command_output', {'command_id': command_id, 'output': "--- Process Started ---", 'type': 'system'})
    
    # Make stdout and stderr non-blocking
    if hasattr(process.stdout, 'fileno'):
        make_non_blocking(process.stdout)
    if hasattr(process.stderr, 'fileno'):
        make_non_blocking(process.stderr)
    
    # Buffers for collecting partial output
    stdout_buffer = b""
    stderr_buffer = b""
    
    while process.poll() is None and not stop_event.is_set():
        # Check if process is still running and not asked to stop
        if process.poll() is not None or stop_event.is_set():
            break
            
        # Try to read from stdout
        stdout_chunk = read_non_blocking(process.stdout)
        if stdout_chunk:
            stdout_buffer += stdout_chunk
            # Process any complete lines
            lines = stdout_buffer.split(b'\n')
            # All lines except possibly the last one are complete
            for line in lines[:-1]:
                decoded_line = line.decode('utf-8', errors='replace').rstrip()
                socketio.emit('command_output', {
                    'command_id': command_id,
                    'output': decoded_line,
                    'type': 'stdout'
                })
                # Sleep a tiny bit to allow the emit to complete
                time.sleep(0.01)
            # Keep any incomplete line in the buffer
            stdout_buffer = lines[-1]
        
        # Try to read from stderr
        stderr_chunk = read_non_blocking(process.stderr)
        if stderr_chunk:
            stderr_buffer += stderr_chunk
            # Process any complete lines
            lines = stderr_buffer.split(b'\n')
            # All lines except possibly the last one are complete
            for line in lines[:-1]:
                decoded_line = line.decode('utf-8', errors='replace').rstrip()
                socketio.emit('command_output', {
                    'command_id': command_id,
                    'output': decoded_line,
                    'type': 'stderr'
                })
                # Sleep a tiny bit to allow the emit to complete
                time.sleep(0.01)
            # Keep any incomplete line in the buffer
            stderr_buffer = lines[-1]
        
        # If no output was received, sleep a bit to avoid CPU thrashing
        if not stdout_chunk and not stderr_chunk:
            time.sleep(0.1)
    
    # Process has ended or been asked to stop
    # Handle any remaining data
    remaining_stdout, remaining_stderr = process.communicate()
    
    # Process any remaining data in buffers
    if stdout_buffer:
        decoded_line = stdout_buffer.decode('utf-8', errors='replace').rstrip()
        if decoded_line:
            socketio.emit('command_output', {
                'command_id': command_id,
                'output': decoded_line,
                'type': 'stdout'
            })
    
    if stderr_buffer:
        decoded_line = stderr_buffer.decode('utf-8', errors='replace').rstrip()
        if decoded_line:
            socketio.emit('command_output', {
                'command_id': command_id,
                'output': decoded_line,
                'type': 'stderr'
            })
    
    # Process any remaining output from communicate()
    if remaining_stdout:
        lines = remaining_stdout.splitlines()
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            socketio.emit('command_output', {
                'command_id': command_id,
                'output': line,
                'type': 'stdout'
            })
    
    if remaining_stderr:
        lines = remaining_stderr.splitlines()
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            socketio.emit('command_output', {
                'command_id': command_id,
                'output': line,
                'type': 'stderr'
            })

    # Notify that the command has completed
    if process.poll() is not None:
        socketio.emit('command_status', {
            'command_id': command_id,
            'status': 'completed',
            'returncode': process.returncode
        })
        socketio.emit('command_output', {
            'command_id': command_id,
            'output': f"--- Process Completed (Return Code: {process.returncode}) ---",
            'type': 'system'
        })
    else:
        socketio.emit('command_status', {
            'command_id': command_id,
            'status': 'stopped',
            'returncode': None
        })
        socketio.emit('command_output', {
            'command_id': command_id,
            'output': "--- Process Stopped ---",
            'type': 'system'
        })

def is_server_command(command):
    """Check if a command is likely to start a server that keeps running"""
    server_patterns = [
        r'flask\s+run',
        r'python\s+.*\.py\s+runserver',
        r'npm\s+start',
        r'node\s+.*server\.js',
        r'serve',
        r'start',
        r'flask',
        r'django',
        r'uvicorn',
        r'webserver',
        r'http-server',
        r'web-server',
        r'dev\s+server',
        r'python\s+.*\.py', # Any Python script could be a server
        r'java',
    ]

    for pattern in server_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            print("is a server command")
            return True
    return False

def run_command_async(command, command_id, project_path):
    """Run a command asynchronously and stream its output"""
    try:
        # Create a stop event for this command
        stop_event = Event()
        command_stop_events[command_id] = stop_event

        # Create the process
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            universal_newlines=False,  # We'll handle decoding ourselves
            bufsize=0,  # No buffering for more real-time output
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Store the process
        active_processes[command_id] = process

        # Notify clients that the command started
        socketio.emit('command_status', {
            'command_id': command_id,
            'status': 'running',
            'is_server': is_server_command(command)
        })

        # Start streaming output in a separate thread
        stream_thread = threading.Thread(
            target=stream_output,
            args=(process, command_id, stop_event)
        )
        stream_thread.daemon = True
        stream_thread.start()

        return True
    except Exception as e:
        logger.error(f"Error starting command: {e}")
        socketio.emit('command_output', {
            'command_id': command_id,
            'output': f"Error: {str(e)}",
            'type': 'error'
        })
        socketio.emit('command_status', {
            'command_id': command_id,
            'status': 'error',
            'error': str(e)
        })
        return False

@app.route('/api/run-command', methods=['POST'])
def run_command():
    """Run a shell command in the project directory"""
    data = request.json
    command = data.get('command')

    if not command:
        return jsonify({
            "success": False,
            "message": "No command provided"
        }), 400

    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)

    try:
        # Limited set of allowed commands for security
        allowed_commands = {
            'python': True,
            'pip': True,
            'pytest': True,
            'npm': True,
            'node': True,
            'ls': True,
            'dir': True,
            'git': True,
            'gcc': True,
            'javac': True,
            'java': True,
        }

        # Simple check to restrict commands
        cmd_parts = command.split()
        if not cmd_parts or cmd_parts[0].lower() not in allowed_commands:
            return jsonify({
                "success": False,
                "message": f"Command not allowed: {cmd_parts[0]}"
            }), 403

        # Generate a unique ID for this command
        command_id = f"cmd_{int(time.time())}_{hash(command) % 10000}"

        # Determine if this is a server command
        is_server = is_server_command(command)

        # For simple commands, run synchronously with a timeout
        if not is_server:
            # Run the command with a timeout
            result = subprocess.run(
                command,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            return jsonify({
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command_id": command_id,
                "is_server": False
            })
        else:
            # For server commands, run asynchronously
            success = run_command_async(command, command_id, project_path)

            if success:
                return jsonify({
                    "success": True,
                    "message": f"Command started with ID: {command_id}",
                    "command_id": command_id,
                    "is_server": True
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to start command"
                }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "message": "Command execution timed out after 30 seconds"
        }), 500
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return jsonify({
            "success": False,
            "message": f"Error running command: {str(e)}"
        }), 500

@app.route('/api/stop-command', methods=['POST'])
def stop_command():
    """Stop a running command"""
    data = request.json
    command_id = data.get('command_id')

    if not command_id or command_id not in active_processes:
        return jsonify({
            "success": False,
            "message": f"No active command found with ID: {command_id}"
        }), 404

    try:
        # Signal the thread to stop
        if command_id in command_stop_events:
            command_stop_events[command_id].set()

        # Get the process
        process = active_processes[command_id]
        pid = process.pid

        # On Windows, we need to kill the entire process tree
        if os.name == 'nt':
            # Use taskkill to force kill the process and all its children
            subprocess.run(f'taskkill /F /T /PID {pid}', shell=True)
        else:
            # On Unix systems
            process.send_signal(signal.SIGTERM)
            time.sleep(1)  # Give it a chance to shut down

            # If still running, force kill
            if process.poll() is None:
                process.kill()

        # Clean up
        del active_processes[command_id]
        if command_id in command_stop_events:
            del command_stop_events[command_id]

        return jsonify({
            "success": True,
            "message": f"Command {command_id} stopped"
        })
    except Exception as e:
        logger.error(f"Error stopping command {command_id}: {e}")
        return jsonify({
            "success": False,
            "message": f"Error stopping command: {str(e)}"
        }), 500

@app.route('/api/list-active-commands', methods=['GET'])
def list_active_commands():
    """List all active commands"""
    try:
        commands = []
        for cmd_id, process in active_processes.items():
            # Check if process is still running
            if process.poll() is None:
                commands.append({
                    "command_id": cmd_id,
                    "status": "running",
                    "pid": process.pid
                })
            else:
                # Process has terminated
                commands.append({
                    "command_id": cmd_id,
                    "status": "completed",
                    "returncode": process.returncode,
                    "pid": process.pid
                })
                # Clean up
                del active_processes[cmd_id]
                if cmd_id in command_stop_events:
                    del command_stop_events[cmd_id]

        return jsonify({
            "success": True,
            "commands": commands
        })
    except Exception as e:
        logger.error(f"Error listing active commands: {e}")
        return jsonify({
            "success": False,
            "message": f"Error listing commands: {str(e)}"
        }), 500

def stop_all_processes():
    """Stop all running processes"""
    for cmd_id, process in list(active_processes.items()):
        try:
            # Signal the thread to stop
            if cmd_id in command_stop_events:
                command_stop_events[cmd_id].set()

            pid = process.pid

            # On Windows, use taskkill to force kill process tree
            if os.name == 'nt':
                subprocess.run(f'taskkill /F /T /PID {pid}', shell=True)
            else:
                # On Unix systems
                process.send_signal(signal.SIGTERM)
                time.sleep(0.5)

                # If still running, force kill
                if process.poll() is None:
                    process.kill()

        except Exception as e:
            logger.error(f"Error stopping command {cmd_id}: {e}")

    # Clear all dictionaries
    active_processes.clear()
    command_stop_events.clear()

@app.route('/api/send-input', methods=['POST'])
def send_input():
    """Send input to a running command"""
    data = request.json
    command_id = data.get('command_id')
    input_text = data.get('input')

    if not command_id or command_id not in active_processes:
        return jsonify({
            "success": False,
            "message": f"No active command found with ID: {command_id}"
        }), 404

    if input_text is None:
        return jsonify({
            "success": False,
            "message": "No input text provided"
        }), 400

    try:
        process = active_processes[command_id]

        # Ensure the process is still running
        if process.poll() is not None:
            return jsonify({
                "success": False,
                "message": f"Command {command_id} has already completed"
            }), 400

        # Add newline if not present
        if not input_text.endswith('\n'):
            input_text += '\n'

        # Send input to the process
        process.stdin.write(input_text.encode('utf-8'))
        process.stdin.flush()

        # Log the input for debugging
        logger.info(f"Input sent to command {command_id}: {input_text.strip()}")

        # Emit the input via Socket.IO so clients can see it
        socketio.emit('command_output', {
            'command_id': command_id,
            'output': f"Input: {input_text.strip()}",
            'type': 'input'
        })

        return jsonify({
            "success": True,
            "message": f"Input sent to command {command_id}"
        })
    except Exception as e:
        logger.error(f"Error sending input to command {command_id}: {e}")
        return jsonify({
            "success": False,
            "message": f"Error sending input: {str(e)}"
        }), 500


def initialize_gemini_chat_for_chatting():
    """Initialize a new chat session with Gemini."""
    global chat
    
    # Configure the model parameters
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 65536,
    }
    
    # Initialize the model
    model_chat = genai.GenerativeModel(
        model_name="gemini-2.5-pro-exp-03-25",
        generation_config=generation_config
    )
    
    # Start a chat session
    chat = model_chat.start_chat(history=[])
    
    return chat


def get_gemini_response(message):
    """Get response from Gemini API."""
    global chat

    prompt="You are Codify agent user is talking to you live, below is his attached message.\nreply briefly as if you are talking to him live. Do not format your response,only return brief response that is very appropriate for speaking.\n\n User Query:"+message
    
    if chat is None:
        initialize_gemini_chat_for_chatting()
    
    try:
        response = chat.send_message(prompt)
        return response.text
    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"


# Add a global variable to track the current thread
global_thread = None

@app.route('/api/talk_live', methods=['POST'])
def chat_endpoint():
    global global_thread
    
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'response': 'No message received'})
    
    # Process in a separate thread to avoid blocking
    def process_request():
        response = get_gemini_response(user_message)
        # In a real-time system, you might send this via WebSockets
        # For simplicity, we'll just return it in the HTTP response
    
    # If there's already a thread running, wait for it to complete
    if global_thread and global_thread.is_alive():
        global_thread.join(timeout=1.0)  # Wait for up to 1 second
    
    # Start a new thread
    global_thread = threading.Thread(target=process_request)
    global_thread.start()
    
    # For immediate response
    response = get_gemini_response(user_message)
    speak_single_message(response)

    return jsonify({'response': response})



@app.route('/api/reset_talking', methods=['POST'])
def reset_chat():
    global chat, global_thread
    
    # Stop the thread if it's running
    if global_thread and global_thread.is_alive():
        # In Python, you can't forcibly terminate a thread safely
        # Best practice is to use a flag or event to signal the thread to stop
        # For simplicity here, we'll just wait for it to complete
        global_thread.join(timeout=2.0)  # Wait up to 2 seconds for thread to finish
    
    # Reset the global thread variable
    global_thread = None
    
    # Reset the chat
    chat = None
    initialize_gemini_chat_for_chatting()
    
    return jsonify({'status': 'Chat session reset'})


@app.route('/api/analyze', methods=['POST'])
def analyze_project():
    """Analyze project files and suggest changes based on user prompt"""
    data = request.json
    user_prompt = data.get('prompt')
    files_to_analyze = data.get('files', [])
    filenames = data.get('filenames',[])
    f_name=""
    if filenames:
        for names_f in filenames:
            f_name += str(names_f)

    if not user_prompt:
        return jsonify({
            "success": False,
            "message": "No prompt provided"
        }), 400

    global model
    if not model:
        # Try to initialize from session or environment
        api_key = session.get('gemini_api_key') or os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')
            except Exception as e:
                return jsonify({
                    "success": False,
                    "message": f"Failed to initialize Gemini API: {str(e)}"
                }), 500
        else:
            return jsonify({
                "success": False,
                "message": "Gemini API not configured properly"
            }), 500

    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)

    # Read the content of selected files
    file_contents = {}
    for file_path in files_to_analyze:
        full_path = os.path.join(project_path, file_path)

        # Check path traversal
        if not os.path.normpath(full_path).startswith(os.path.normpath(project_path)):
            continue
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                file_contents[file_path] = str(f.read())
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {e}")
            file_contents[file_path] = f"[Error reading file: {str(e)}]"

    # Prepare the prompt for Gemini
    analysis_prompt = f"""
    You are an AI assistant for analyzing and improving code projects. A user has the following request:

    "{user_prompt}"

    Here are the relevant files from the project:

    {json.dumps(file_contents, indent=2) +" " +f_name}

    Based on the user's request, analyze these files and provide:
    1. A summary of what you've found. Remember user is on windows machine.
    2. Specific changes you recommend for each file(only if file content is passsed and need changes)
    3. If any libraries are to be installed also include them as modification.
    4. Any terminal commands that need to be executed (give in order of execution)(like installing packages, starting services, etc.)
    5. The complete file code with updated content for each file that needs changes is to be returned in modifed filed.
    6. Do not introduce or conclude your response just return correct json as below. Always if needed return command to run the file like python app.py
    7. If you are making a web app based on flask. run it using webbrowser python library.(not on port 5000)
    8. Do not the return file in change key if that file do not require modification.(return files that need modifications)
    9. Do not concider "Exit code: undefined" to be error.
    10. If vision model summary is given also concider it (when solving error)
    11. If user want to create files like- docx, pptx, json, excel, etc remember you have complete access to users terminal (where you can run commands) and file paths. Give python script to create the desired file and incorporate the desired content user asked in the file and create the file. Remember while creating documents do not include elements like fonts that can cause error due to missing fonts in some system try to use elements available universally for minimum errors (This instruction is just for file creation of format like docx, pptx, excel, etc)


    Strictly Format your response as valid JSON with these keys:
    {{
        "summary": "Your analysis summary",
        "need_intervention":'True' ( When code is running perfectly or when code cannot be automatically fixed by AI or need human intervnetion) or 'False' (when ai can fix errors and human intervention is not needed )
        "commands": [
            {{
                "command": "terminal command to run",
                "explanation": "why this command is needed",
                "isRequired": true/false
            }}
        ],
        "changes": [
            {{
                "file": "path/to/file",
                "original": "original wrong content of respective file(not full file just the old part which has error/need improvement)",
                "modified": "modified complete file content(do not give only modified part give full modified file)",
                "explanation": "explanation of changes"
            }}
        ]
    }}
    """

    try:
        # Call Gemini API
        generation_config = {
            "max_output_tokens": 65536,
            "response_mime_type":"application/json"
        }
        response = model.generate_content(analysis_prompt, generation_config=generation_config)
        response_text = response.text

        # Extract JSON from the response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            response_json = json.loads(json_match.group(1))
        else:
            # Try parsing the whole response as JSON
            try:
                response_json = json.loads(response_text)
            except:
                # If not valid JSON, create a structured response
                return jsonify({
                    "success": True,
                    "data": {
                        "summary": "The AI generated a non-JSON response. Here's the raw output:",
                        "commands": [],
                        "changes": [],
                        "raw_response": response_text
                    }
                })

        # Ensure commands field exists
        if "commands" not in response_json:
            response_json["commands"] = []

        return jsonify({
            "success": True,
            "data": response_json
        })
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return jsonify({"success": False,
            "message": f"Error analyzing project: {str(e)}"
        }), 500






@app.route('/gitmain')
def gitmain():
    """Home page that shows the Git tree visualization."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    
    # Check if the project path exists
    if not os.path.exists(project_path):
        return render_template('setup.html', error=f"Project path {project_path} does not exist")
    
    # Check if git is initialized
    is_git_initialized = os.path.exists(os.path.join(project_path, '.git'))
    
    if not is_git_initialized:
        return render_template('setup.html', project_path=project_path, git_status="not_initialized")
    
    # Get repository info using pygit2
    try:
        repo = pygit2.Repository(os.path.join(project_path, '.git'))
        current_branch = None
        commits = []
        status = []
        
        # Check if repository has any commits safely
        try:
            # Check if the repository is empty
            if repo.is_empty:
                current_branch = "No commits yet"
                has_commits = False
            else:
                # Try to get the current branch
                try:
                    head_ref = repo.head
                    # Different versions of pygit2 might handle this differently
                    if hasattr(head_ref, 'is_detached'):
                        is_detached = head_ref.is_detached
                    else:
                        # Alternative approach for different pygit2 versions
                        is_detached = head_ref.name == 'HEAD'
                    
                    if not is_detached:
                        current_branch = head_ref.shorthand
                        has_commits = True
                    else:
                        current_branch = "HEAD detached"
                        has_commits = True
                except (pygit2.GitError, KeyError, AttributeError):
                    current_branch = "No commits yet"
                    has_commits = False
                
                # Get commits history only if we have commits
                if has_commits:
                    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
                        commits.append({
                            'id': str(commit.id)[:7],
                            'full_id': str(commit.id),
                            'message': commit.message.strip(),
                            'author': commit.author.name,
                            'time': datetime.fromtimestamp(commit.commit_time).strftime('%Y-%m-%d %H:%M:%S'),
                            'is_current': str(commit.id) == str(repo.head.target)
                        })
        except Exception as e:
            current_branch = "Error detecting branch"
            has_commits = False
            print(f"Error when checking repository status: {str(e)}")
        
        # Get list of branches
        branches = []
        for branch_name in repo.branches.local:
            branches.append(branch_name)
        
        # Check for modified files
        for filepath, flags in repo.status().items():
            status_desc = get_status_description(flags)
            status.append({
                'path': filepath,
                'status': status_desc
            })
            
        return render_template('gitmain.html', 
                              project_path=project_path,
                              current_branch=current_branch,
                              branches=branches,
                              commits=commits,
                              status=status)
    except Exception as e:
        return render_template('error.html', error=str(e))
    
    
def get_status_description(status_flags):
    """Convert pygit2 status flags to human-readable description."""
    if status_flags & pygit2.GIT_STATUS_INDEX_NEW:
        return "New (staged)"
    elif status_flags & pygit2.GIT_STATUS_INDEX_MODIFIED:
        return "Modified (staged)"
    elif status_flags & pygit2.GIT_STATUS_INDEX_DELETED:
        return "Deleted (staged)"
    elif status_flags & pygit2.GIT_STATUS_WT_NEW:
        return "New (unstaged)"
    elif status_flags & pygit2.GIT_STATUS_WT_MODIFIED:
        return "Modified (unstaged)"
    elif status_flags & pygit2.GIT_STATUS_WT_DELETED:
        return "Deleted (unstaged)"
    else:
        return "Unknown"



@app.route('/git_init', methods=['POST'])
def git_init():
    """Initialize a new Git repository."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    try:
        subprocess.run(['git', 'init'], cwd=project_path, check=True)
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        return render_template('error.html', error=f"Git init failed: {str(e)}")

@app.route('/git_stage_all', methods=['POST'])
def git_stage_all():
    """Stage all changes."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    try:
        subprocess.run(['git', 'add', '.'], cwd=project_path, check=True)
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        return render_template('error.html', error=f"Staging failed: {str(e)}")

@app.route('/git_commit', methods=['POST'])
def git_commit():
    """Commit staged changes."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    commit_message = request.form.get('commit_message', 'Update')
    try:
        # Stage all changes if requested
        if request.form.get('stage_all'):
            subprocess.run(['git', 'add', '.'], cwd=project_path, check=True,capture_output=True)
        
        # Perform the commit
        subprocess.run(['git', 'commit', '-m', commit_message], cwd=project_path, check=True,capture_output=True)
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        git_error = e.stderr
        return render_template('error.html', error=f"Commit failed: {git_error}")

@app.route('/git_push', methods=['POST'])
def git_push():
    """Push commits to remote."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    try:
        # Get the current branch
        repo = pygit2.Repository(os.path.join(project_path, '.git'))
        
        try:
            head_ref = repo.head
            if hasattr(head_ref, 'shorthand'):
                current_branch = head_ref.shorthand
            else:
                # Alternative method to get branch name
                current_branch = head_ref.name.replace('refs/heads/', '')
        except (pygit2.GitError, AttributeError):
            return render_template('error.html', error="Cannot determine current branch. Make sure you have commits.")
        
        # Push to remote
        result = subprocess.run(['git', 'push', 'origin', current_branch], 
                               cwd=project_path, 
                               capture_output=True, 
                               text=True)
        
        if result.returncode != 0:
            if "remote origin already exists" in result.stderr:
                return render_template('error.html', error="Remote already exists. Try pushing again.")
            elif "no configured push destination" in result.stderr:
                # Remote is not set up
                return render_template('setup_remote.html', project_path=project_path)
            else:
                return render_template('error.html', error=f"Push failed: {result.stderr}")
        
        return redirect(url_for('gitmain'))
    except Exception as e:
        return render_template('error.html', error=f"Push failed: {str(e)}")

@app.route('/setup_remote', methods=['POST'])
def setup_remote():
    """Set up a remote repository."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    remote_url = request.form.get('remote_url')
    
    try:
        # Check if remote already exists
        result = subprocess.run(['git', 'remote'], cwd=project_path, capture_output=True, text=True, check=True)
        
        if 'origin' in result.stdout.split():
            # Remove existing remote
            subprocess.run(['git', 'remote', 'remove', 'origin'], cwd=project_path, check=True,capture_output=True)
        
        # Add new remote
        subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=project_path, check=True,capture_output=True)
        
        # Get current branch name safely
        repo = pygit2.Repository(os.path.join(project_path, '.git'))
        try:
            head_ref = repo.head
            if hasattr(head_ref, 'shorthand'):
                current_branch = head_ref.shorthand
            else:
                current_branch = head_ref.name.replace('refs/heads/', '')
                
            # Set upstream for current branch
            result=subprocess.run(['git', 'push', '--set-upstream', 'origin', current_branch], 
                          cwd=project_path, check=True,capture_output=True)
        except (pygit2.GitError, AttributeError):
            return render_template('error.html', error=f"Cannot determine current branch. Make sure you have commits.")
        
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        git_error = e.stderr
        return render_template('error.html', error=f"Remote setup failed: {git_error}")

@app.route('/checkout_commit/<commit_id>', methods=['POST'])
def checkout_commit(commit_id):
    """Checkout to a specific commit."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    try:
        result = subprocess.run(['git', 'checkout', commit_id], cwd=project_path, check=True,capture_output=True)
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        git_error = e.stderr
        return render_template('error.html', error=f"Checkout failed: {git_error}")

@app.route('/checkout_branch/<branch_name>', methods=['POST'])
def checkout_branch(branch_name):
    """Checkout to a specific branch."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    try:
        # Capture both stdout and stderr from the git command
        result = subprocess.run(
            ['git', 'checkout', branch_name], 
            cwd=project_path, 
            check=True,
            capture_output=True,
            text=True
        )
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        # Get the actual git error message from stderr
        git_error = e.stderr
        return render_template('error.html', error=f"Checkout failed: {git_error}")

@app.route('/create_branch', methods=['POST'])
def create_branch():
    """Create a new branch."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    branch_name = request.form.get('branch_name')
    checkout = request.form.get('checkout', 'false') == 'true'
    
    try:
        # Create branch
        subprocess.run(['git', 'branch', branch_name], cwd=project_path, check=True)
        
        # Checkout if requested
        if checkout:
            subprocess.run(['git', 'checkout', branch_name], cwd=project_path, check=True)
        
        return redirect(url_for('gitmain'))
    except subprocess.CalledProcessError as e:
        return render_template('error.html', error=f"Branch creation failed: {str(e)}")

@app.route('/get_git_graph')
def get_git_graph():
    """Get Git graph data in JSON format for visualization."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    
    try:
        # Check if repository has any commits first
        repo = pygit2.Repository(os.path.join(project_path, '.git'))
        if repo.is_empty:
            return jsonify({
                'nodes': [],
                'links': []
            })
            
        # Get git log with graph format
        result = subprocess.run(
            ['git', 'log', '--graph', '--oneline', '--decorate', '--all', '--date-order'],
            cwd=project_path, capture_output=True, text=True, check=True
        )
        
        # Parse the git log output into a structure suitable for visualization
        graph_lines = result.stdout.strip().split('\n')
        
        # Convert the ASCII graph to a structured format for D3.js visualization
        nodes = []
        links = []
        
        for i, line in enumerate(graph_lines):
            # Extract commit hash and message
            match = re.search(r'\*\s+([0-9a-f]+)\s+(.*)', line)
            if match:
                commit_hash = match.group(1)
                commit_message = match.group(2)
                nodes.append({
                    'id': commit_hash,
                    'message': commit_message,
                    'level': i
                })
                
                # Try to find parent connections based on the ASCII graph
                for j in range(i+1, min(i+5, len(graph_lines))):
                    parent_match = re.search(r'\*\s+([0-9a-f]+)', graph_lines[j])
                    if parent_match and '|' in graph_lines[j-1]:
                        links.append({
                            'source': commit_hash,
                            'target': parent_match.group(1)
                        })
                        break
        
        return jsonify({
            'nodes': nodes,
            'links': links
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/file_history/<path:file_path>')
def file_history(file_path):
    """Show the commit history for a specific file."""
    project_path = session.get('project_path', DEFAULT_PROJECT_DIR)
    
    try:
        repo = pygit2.Repository(os.path.join(project_path, '.git'))
        file_history = []
        history_exists = False
        
        # Make sure the file path is relative to the repository
        if file_path.startswith(project_path):
            file_path = os.path.relpath(file_path, project_path)
        
        # Check if the file currently exists in the repository
        file_exists_now = os.path.exists(os.path.join(project_path, file_path))
        
        # First, check if file ever existed in repository history
        try:
            # Try to find the file in the current HEAD
            if not repo.is_empty:
                try:
                    # This will raise KeyError if the file doesn't exist in HEAD
                    repo.revparse_single('HEAD').tree[file_path]
                    history_exists = True
                except KeyError:
                    # File might have existed in the past but was deleted
                    # We need to search through history
                    pass
            
            # If not found in HEAD or we're not sure, search through all commits
            if not history_exists and not repo.is_empty:
                for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
                    try:
                        # Check if file exists in this commit
                        commit.tree[file_path]
                        history_exists = True
                        break
                    except KeyError:
                        # Check if it was modified (added/deleted) in this commit
                        if commit.parents:
                            diff = repo.diff(commit.parents[0], commit)
                            for patch in diff:
                                if (patch.delta.new_file.path == file_path or 
                                    patch.delta.old_file.path == file_path):
                                    history_exists = True
                                    break
                            if history_exists:
                                break
        except Exception as e:
            print(f"Error checking file history: {str(e)}")
        
        # If history exists, collect the actual history
        if history_exists:
            # [Your existing code to collect file_history]
            for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
                # Check if this commit modified the file
                parent_ids = [p.id for p in commit.parents]
                if not parent_ids:  # Initial commit
                    try:
                        entry = commit.tree[file_path]
                        file_history.append({
                            'id': str(commit.id)[:7],
                            'full_id': str(commit.id),
                            'message': commit.message.strip(),
                            'author': commit.author.name,
                            'time': datetime.fromtimestamp(commit.commit_time).strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'added'
                        })
                    except KeyError:
                        # File didn't exist in the initial commit
                        pass
                else:
                    # Compare with parent to see if file was modified
                    parent = repo[parent_ids[0]]
                    diff = repo.diff(parent, commit)
                    
                    for patch in diff:
                        if (patch.delta.new_file.path == file_path or 
                            patch.delta.old_file.path == file_path):
                            
                            change_type = 'modified'
                            if patch.delta.is_binary:
                                content_diff = "Binary file"
                            else:
                                content_diff = patch.text
                                
                            # Determine if file was added, deleted or modified
                            if patch.delta.status == pygit2.GIT_DELTA_ADDED:
                                change_type = 'added'
                            elif patch.delta.status == pygit2.GIT_DELTA_DELETED:
                                change_type = 'deleted'
                                
                            file_history.append({
                                'id': str(commit.id)[:7],
                                'full_id': str(commit.id),
                                'message': commit.message.strip(),
                                'author': commit.author.name,
                                'time': datetime.fromtimestamp(commit.commit_time).strftime('%Y-%m-%d %H:%M:%S'),
                                'type': change_type,
                                'diff': content_diff if not patch.delta.is_binary else None
                            })
                            break
        
        return render_template('file_history.html', 
                              file_path=file_path,
                              project_path=project_path, 
                              history=file_history,
                              history_exists=history_exists,
                              file_exists_now=file_exists_now)
                              
    except Exception as e:
        return render_template('error.html', error=str(e))













# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")


def run_server():
    """Run the Flask server"""
    # Start with a clean state
    stop_all_processes()
    
    # Load environment variables
    load_dotenv()
    
    # Initialize Gemini API
    initialize_gemini()
    
    # Define host and port
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "127.0.0.1")
    
    # Run the server with Socket.IO
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)



def create_window():
    """Create a PyWebView window pointing to the Flask app"""
    try:
        # Create the Flask server in a separate thread
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for the server to start
        time.sleep(1)
        
        # Create the window
        webview.create_window(
            title="Codify - Ayushman",
            url="http://127.0.0.1:5000",
            width=1200,
            height=800,
            resizable=True,
            min_size=(850, 600),
            confirm_close=True
        )
        
        # Start the window main loop
        webview.start()
        
        # Clean up when window is closed
        stop_all_processes()
        os._exit(0)
    except Exception as e:
        logger.error(f"Error creating window: {e}")
        os._exit(1)

if __name__ == "__main__":
    # Check if running as a script or frozen executable
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        application_path = os.path.dirname(sys.executable)
    else:
        # Running as script
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(application_path)
    
    # Create and start the window
    create_window()


##final working project