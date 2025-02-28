from flask import Flask, render_template, request, jsonify, session, redirect, url_for
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

def initialize_gemini():
    """Initialize Gemini API with API key from environment variables"""
    global model

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.error(f"Error configuring Gemini API: {e}")
            model = None
    else:
        logger.warning("No Gemini API key found in environment variables")
        model = None

@app.route('/api/set-api-key', methods=['POST'])
def set_api_key():
    """Set the Gemini API key"""
    global model

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
    global model

    if model is None and 'gemini_api_key' in session:
        api_key = session['gemini_api_key']
        try:
            genai.configure(api_key=api_key)
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
        import fcntl
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
        r'python\s+.*\.py'  # Any Python script could be a server
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

    Strictly Format your response as valid JSON with these keys:
    {{
        "summary": "Your analysis summary",
        "need_intervention":"'True' (when code cannot be automatically fixed by AI or need human intervnetion) or 'False' (when code is fixed and returns no error)"
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
            "max_output_tokens": 100000,
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
            min_size=(800, 600),
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


##final working