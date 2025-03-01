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


class ScreenAnalyzer:
    """Handles screen capture and AI analysis."""

    def __init__(self, api_key):
        # Configuration
        self.frame_interval = 0.033  # ~30 FPS
        self.gemini_interval = 0.5  # Rate of Gemini updates
        self.cooldown_period = 3.0  # Time to wait before restarting stream

        # Initialize state
        self.frame = None
        self.frame_lock = Lock()
        self.response_text = ""
        self.response_lock = Lock()
        self.streaming = False
        self.stop_flag = False
        self.last_stop_time = 0

        # Initialize Gemini model
        self._initialize_model(api_key)

    def _initialize_model(self, api_key):
        """Initialize the Gemini model with the provided API key."""
        genai.configure(api_key=api_key)

        # Model configuration
        generation_config = {
            "temperature": 0.4,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 4096,
        }

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-002",  # Changed model name to a valid one.  Use a *pro* model if you need vision.
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    def start_stream(self, prompt):
        """Start screen capture and analysis streams."""
        current_time = time.time()

        # Prevent rapid restart
        if current_time - self.last_stop_time < self.cooldown_period:
            return False, "Please wait a few seconds before restarting."

        if self.streaming:
            return False, "Streaming is already active."

        # Reset state
        self.streaming = True
        self.stop_flag = False
        with self.response_lock:
            self.response_text = ""

        # Start capture thread
        capture_thread = Thread(target=self._capture_screen)
        capture_thread.daemon = True
        capture_thread.start()

        # Wait for first frame
        time.sleep(0.5)

        # Start analysis thread
        prompt_parts = [f"""
    Here is a live stream of my screen, respond concisely with only essential information given below:
    You are Codify agent response accordindly.
    \n{prompt}\n

    Instructions:
    1. By alalyzing the current screen, initial query of the user determine if the task is successfully completed or not.
    2. Do not concider "Exit code: undefined" to be error.
    3. If the request is fulfilled and app runs perfectly(return value of vison_stop_agent as 'True')
    4. If errors cant be resolved after many tries (return value of vison_stop_agent as 'True')
    5. If program need human intervention (return value of vison_stop_agent as 'True')
    6. If you are satisfied that there are no errors and code runs fine, after you observe desired task is running correctly then only return 'True'
    in all other cases like solving errors return 'False'
    7. Do not indroduce or conclude your response just return json
    return a JSON with following keys:

    Strictly Format your response as valid JSON with these keys:
    {{
        "summary": "Your detailed summary of contents you see on screen and analysis on above instructions",
        "vison_stop_agent":'True' (when code is running perfectly according to initial prompt and whatever you see on screen(check thouroughly that the app is working according to initial request and screen output then only return 'True' ) /(or) when code cannot be automatically fixed by AI then return 'True' /(or) need human intervnetion to fix then return 'True' ) else return 'False' (in all other cases)
    }}
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
        return True, "Streaming stopped."

    def is_streaming(self):
        """Check if streaming is active."""
        return self.streaming

    def get_frame_interval(self):
        """Get the frame interval."""
        return self.frame_interval

    def get_response(self):
        """Get the current AI response."""
        with self.response_lock:
            print("Raw response:", self.response_text)
            
            # First, try to clean the response if it contains markdown code blocks
            cleaned_text = self.response_text
            
            # Remove markdown code blocks if present
            json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', cleaned_text)
            if json_block_match:
                cleaned_text = json_block_match.group(1).strip()
            
            # Try parsing the cleaned JSON
            try:
                response_json = json.loads(cleaned_text)
                return response_json
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e} for text: {cleaned_text}")
                
                # Last resort: try to find any JSON-like structure with curly braces
                json_pattern = re.search(r'({[\s\S]*?})', cleaned_text)
                if json_pattern:
                    try:
                        potential_json = json_pattern.group(1)
                        response_json = json.loads(potential_json)
                        return response_json
                    except json.JSONDecodeError:
                        pass  # Fall through to the error message
            
            # If we get here, we couldn't parse the JSON
            return {
                "summary": " " + self.response_text[:200],
                "vison_stop_agent": "False"
            }


    def get_encoded_frame(self):
        """Get the current frame as base64 encoded JPEG."""
        with self.frame_lock:
            if self.frame is None:
                return None
            frame_copy = self.frame.copy()

        _, buffer = cv2.imencode('.jpg', frame_copy)
        return base64.b64encode(buffer).decode('utf-8')

    def _capture_screen(self):
        """Thread function for screen capture."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor

            while not self.stop_flag and self.streaming:
                # Capture screenshot
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Update frame
                with self.frame_lock:
                    self.frame = frame

                time.sleep(self.frame_interval)

    def _analyze_frames(self, prompt_parts):
        """Thread function for AI analysis."""
        while not self.stop_flag and self.streaming:
            with self.frame_lock:
                if self.frame is None:
                    time.sleep(0.1)
                    continue
                frame_copy = self.frame.copy()

            # Encode image for Gemini
            _, encoded_frame = cv2.imencode('.jpg', frame_copy)
            img_data = encoded_frame.tobytes()
            image_part = {"mime_type": "image/jpeg", "data": img_data}

            try:
                # Send to Gemini
                current_prompt = prompt_parts + [image_part]
                response = self.model.generate_content(current_prompt, stream=True)
                # print(response)
                #  Iterate through the response chunks and build up the text.
                full_response_text = ""
                for chunk in response:
                    full_response_text += chunk.text
                
                # Update response
                with self.response_lock:
                    self.response_text = full_response_text

            except Exception as e:
                with self.response_lock:
                    self.response_text = f"Error: {e}"
                    print(f"Error in Gemini interaction: {e}")

            time.sleep(self.gemini_interval)