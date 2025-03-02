import time
import base64
from threading import Thread, Lock
import re
import cv2
import numpy as np
import mss
import mss.tools
import google.generativeai as genai
from flask import jsonify
import json
import pyttsx3
import queue


class ScreenAnalyzer:
    """Handles screen capture and AI analysis with speech-optimized responses."""

    def __init__(self, api_key):
        # Configuration with optimized performance
        self.frame_interval = 0.033  # ~30 FPS (1/30 = 0.033)
        self.gemini_interval = 1.0   # Fetch Gemini responses every 1 second
        self.cooldown_period = 5.0   # Shorter cooldown
        self.voice_interval = 1    # More frequent voice feedback

        # Initialize state
        self.frame = None
        self.frame_lock = Lock()
        self.response_text = ""
        self.response_lock = Lock()
        self.streaming = False
        self.stop_flag = False
        self.last_stop_time = 0
        
        # Voice related variables
        self.speech_queue = []
        self.speech_lock = Lock()
        self.speaking = False
        self.last_voice_time = 0
        self.last_spoken_text = ""
        self.voice_thread = None
        self.debug_mode = False  # Enable debug mode to print voice info
        
        # Frame processing
        self.last_processed_frame_time = 0
        self.frame_process_interval = 1.0  # Process frames every 1 second
        
        # Initialize Gemini model
        self._initialize_model(api_key)

    def _initialize_model(self, api_key):
        """Initialize the Gemini model with the provided API key."""
        genai.configure(api_key=api_key)

        # Model configuration 
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.9,
            "top_k": 32,
            "max_output_tokens": 2048,
            "response_mime_type":"application/json",
        }

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    def start_stream(self, prompt):
        """Start screen capture and analysis streams."""
        current_time = time.time()

        if current_time - self.last_stop_time < self.cooldown_period:
            return False, "Please wait a moment before restarting."

        if self.streaming:
            return False, "Streaming is already active."

        # Reset state
        self.streaming = True
        self.stop_flag = False
        with self.response_lock:
            self.response_text = ""
            
        # Start voice thread if needed
        if self.voice_thread is None or not self.voice_thread.is_alive():
            self.voice_thread = Thread(target=self._speak_latest)
            self.voice_thread.daemon = True
            self.voice_thread.start()
            if self.debug_mode:
                print("Voice thread started")

        # Ensure initial voice announcement works
        self._add_to_speech_queue("Analysis started")
        if self.debug_mode:
            print("Added 'Analysis started' to speech queue")
        
        # Start capture thread
        capture_thread = Thread(target=self._capture_screen)
        capture_thread.daemon = True
        capture_thread.start()

        # Wait briefly for first frame
        time.sleep(0.2)

        # Start analysis thread - KEEP ORIGINAL PROMPT but add screen_voice request
        prompt_parts = [f"""
    Analyze my screen's live stream and respond concisely with only essential information.  You are acting as the Codify agent.

    \n{prompt}\n

    **Instructions:**

    1.  Assess if the initial user query's task has been successfully completed by analyzing the screen.
    2.  Disregard "Exit code: undefined" as an error.
    3.  Return `"vison_stop_agent": "True"` **only if** the request is fulfilled and the application runs perfectly.
    4.  Return `"vison_stop_agent": "True"` if unresolvable errors persist after multiple attempts.
    5.  Return `"vison_stop_agent": "True"` if the program requires human intervention.
    6.  Return `"vison_stop_agent": "True"` **only** after verifying the desired task is running correctly and free of errors.
    7.  Otherwise, return `"vison_stop_agent": "False"`.  Do not provide introductory or concluding remarks.

    **JSON Response Format:**

    Your response **must** be valid JSON with the following keys:

    ```json
    {{
        "summary": "A detailed summary of the screen's contents and your analysis based on the instructions.",
        "vison_stop_agent": "True" or "False" (as described above),
        "screen_voice": "Act as the Codify AI agent, assisting users with their projects. Refer to Codify's actions in the first person. Provide concise updates based on the screen's content. If another window is visible, prompt the user to switch to the Codify app (Description of Codify app: it has '</>' logo and blue and white (majorly) as color pallete). Keep responses brief and suitable for text-to-speech."
    }}
    ```

    Ensure `"screen_voice"` is extremely concise for text-to-speech.
    """]
        analysis_thread = Thread(target=self._analyze_frames, args=(prompt_parts,))
        analysis_thread.daemon = True
        analysis_thread.start()

        return True, "Streaming started."

    def stop_stream(self):
        """Stop screen capture and analysis."""
        self.stop_flag = True
        self.streaming = False
        self.last_stop_time = time.time()
        self._add_to_speech_queue("Analysis stopped")
        if self.debug_mode:
            print("Added 'Analysis stopped' to speech queue")
        return True, "Streaming stopped."

    def is_streaming(self):
        """Check if streaming is active."""
        return self.streaming

    def get_frame_interval(self):
        """Get the frame interval."""
        return self.frame_interval

    def get_response(self):
        """Get the current AI response with improved JSON parsing."""
        with self.response_lock:
            # Try to clean and parse the response
            cleaned_text = self.response_text
            
            # Remove markdown code blocks if present
            json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', cleaned_text)
            if json_block_match:
                cleaned_text = json_block_match.group(1).strip()
            
            # Try parsing as JSON
            try:
                response_json = json.loads(cleaned_text)
                
                # Process for voice output using the new screen_voice field
                self._process_response_for_voice(response_json)
                
                return response_json
            except json.JSONDecodeError:
                # Extract JSON-like structure with regex
                json_pattern = re.search(r'({[\s\S]*?})', cleaned_text)
                if json_pattern:
                    try:
                        potential_json = json_pattern.group(1)
                        response_json = json.loads(potential_json)
                        self._process_response_for_voice(response_json)
                        return response_json
                    except json.JSONDecodeError:
                        pass
            
            # Default response if parsing failed
            default_response = {
                "summary": self.response_text[:150] + "..." if len(self.response_text) > 150 else self.response_text,
                "vison_stop_agent": "False",
                "screen_voice": "Processing screen, please wait..."
            }
            
            self._process_response_for_voice(default_response)
            return default_response

    def get_encoded_frame(self):
        """Get the current frame as base64 encoded JPEG with optimized compression."""
        with self.frame_lock:
            if self.frame is None:
                return None
            frame_copy = self.frame.copy()

        # Optimize encoding for speed
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 80]  
        _, buffer = cv2.imencode('.jpg', frame_copy, encode_params)
        return base64.b64encode(buffer).decode('utf-8')
        
    def _process_response_for_voice(self, response_json):
        """Process the response JSON for voice using the dedicated screen_voice field."""
        current_time = time.time()
        
        # Only process if enough time has passed
        if current_time - self.last_voice_time < self.voice_interval:
            return
            
        # Use the dedicated screen_voice field if available
        screen_voice = response_json.get("screen_voice", "")
        
        # Fall back to summary if screen_voice is missing
        if not screen_voice:
            summary = response_json.get("summary", "")
            if summary:
                screen_voice = self._create_speech_summary(summary)
        
        # Don't repeat the same text
        if screen_voice and screen_voice != self.last_spoken_text:
            self._add_to_speech_queue(screen_voice)
            self.last_spoken_text = screen_voice
            self.last_voice_time = current_time
            if self.debug_mode:
                print(f"Added to speech queue: {screen_voice}")
            
    def _create_speech_summary(self, summary):
        """Create a brief speech summary when screen_voice is not available."""
        if not summary:
            return ""
            
        # Clean up the text
        cleaned = re.sub(r'https?://\S+', '', summary)
        cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Get first sentence
        sentences = re.split(r'[.!?]', cleaned)
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 80:  # Even shorter for speech
                return first_sentence[:77] + "..."
            return first_sentence
        
        return cleaned[:80] + "..." if len(cleaned) > 80 else cleaned

    def _speak_latest(self):
        """Thread function to speak the latest message in the queue."""
        while True:
            if not self.streaming or self.stop_flag:
                time.sleep(0.1)
                continue
            with self.speech_lock:
                if self.speech_queue and not self.speaking:
                    # Get the latest message (last in queue)
                    latest_message = self.speech_queue[-1]
                    self.speech_queue = []  # Clear queue after grabbing latest
                    self.speaking = True
            if self.speaking:
                try:
                    # Create a new speech engine instance each time
                    speech_engine = pyttsx3.init()
                    # Set voice properties - recreated for each instance
                    speech_engine.setProperty('rate', 200)  # Faster speech
                    speech_engine.setProperty('volume', 1.0)  # Full volume
                    
                    print(f"Speaking at {time.strftime('%H:%M:%S')}: {latest_message}")
                    speech_engine.say(latest_message)
                    speech_engine.runAndWait()
                except Exception as e:
                    print(f"Speech error: {e}")
                finally:
                    print(f"Finished speaking at {time.strftime('%H:%M:%S')}")
                    with self.speech_lock:
                        self.speaking = False
            time.sleep(0.1)  # Small delay to prevent tight looping

    def _add_to_speech_queue(self, text):
        """Add text to speech queue, prioritizing newest information."""
        if not text:
            return
            
        try:
            with self.speech_lock:
                # Add to queue, keeping only most recent items (max 3)
                self.speech_queue.append(text)
                if len(self.speech_queue) > 3:
                    self.speech_queue = self.speech_queue[-3:]
                    
            if self.debug_mode:
                print(f"Added to speech queue: {text}, queue size: {len(self.speech_queue)}")
        except Exception as e:
            print(f"Queue error: {e}")

    def _capture_screen(self):
        """Thread function for optimized screen capture."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor

            while not self.stop_flag and self.streaming:
                # Capture screenshot
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                
                # Resize large screens for better performance
                height, width = frame.shape[:2]
                if width > 1920 or height > 1080:
                    scale = min(1920/width, 1080/height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Update frame
                with self.frame_lock:
                    self.frame = frame

                time.sleep(self.frame_interval)  # Adjusted for 30 FPS

    def _analyze_frames(self, prompt_parts):
        """Thread function for AI analysis with intelligent response handling."""
        last_screen_voice = ""
        
        while not self.stop_flag and self.streaming:
            current_time = time.time()
            
            # Process frames at controlled intervals
            if current_time - self.last_processed_frame_time < self.frame_process_interval:
                time.sleep(0.01)
                continue
                
            self.last_processed_frame_time = current_time
            
            with self.frame_lock:
                if self.frame is None:
                    time.sleep(0.05)
                    continue
                frame_copy = self.frame.copy()

            # Encode image with optimized quality
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
            _, encoded_frame = cv2.imencode('.jpg', frame_copy, encode_params)
            img_data = encoded_frame.tobytes()
            image_part = {"mime_type": "image/jpeg", "data": img_data}

            try:
                # Send to Gemini
                current_prompt = prompt_parts + [image_part]
                response = self.model.generate_content(current_prompt, stream=True)
                
                accumulated_text = ""
                
                # Process streaming response efficiently
                for chunk in response:
                    if self.stop_flag:
                        break
                        
                    if chunk.text:
                        accumulated_text += chunk.text
                        
                        # Update response text frequently
                        with self.response_lock:
                            self.response_text = accumulated_text
                        
                        # Check for complete JSON response to break early
                        if all(key in accumulated_text for key in ['"summary":', '"vison_stop_agent":', '"screen_voice":']):
                            if accumulated_text.strip().endswith('}'):
                                break
                
                # Final update
                with self.response_lock:
                    self.response_text = accumulated_text
                
                # Force voice feedback for new analyses
                try:
                    response_json = json.loads(accumulated_text)
                    screen_voice = response_json.get("screen_voice", "")
                    
                    # Only speak if it's different from the last one
                    if screen_voice and screen_voice != last_screen_voice:
                        self._add_to_speech_queue(screen_voice)
                        last_screen_voice = screen_voice
                        if self.debug_mode:
                            print(f"Forced voice feedback: {screen_voice}")
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error processing voice feedback: {e}")

            except Exception as e:
                error_msg = str(e)
                print(f"Gemini error: {error_msg}")
                
                # Create error JSON with all required fields including screen_voice
                error_voice = "Analysis error. Retrying."
                with self.response_lock:
                    self.response_text = json.dumps({
                        "summary": f"Error in analysis: {error_msg[:100]}",
                        "vison_stop_agent": "False",
                        "screen_voice": error_voice
                    })
                
                # Force error voice feedback
                if error_voice != last_screen_voice:
                    self._add_to_speech_queue(error_voice)
                    last_screen_voice = error_voice

            # Use the adjusted 1-second interval between Gemini requests
            time.sleep(self.gemini_interval)