const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
// const promptInput = document.getElementById('prompt');
// const streamImage = document.getElementById('streamImage');
// const streamPlaceholder = document.getElementById('streamPlaceholder');
// const responseContainer = document.getElementById('responseContainer');
// const statusDot = document.getElementById('statusDot');
// const statusText = document.getElementById('statusText');
const statusMessage = document.getElementById('statusMessage');

// State variables
let isStreaming = false;
let responseInterval = null;

// Functions
function updateUIState(streaming) {
    isStreaming = streaming;

    startBtn.disabled = streaming;
    stopBtn.disabled = !streaming;
    // promptInput.disabled = streaming;

    // statusDot.classList.toggle('active', streaming);
    // statusText.textContent = streaming ? 'Streaming active' : 'Not streaming';

    // if (streaming) {
    //     streamImage.style.display = 'block';
    //     streamPlaceholder.style.display = 'none';
    //     responseContainer.textContent = 'Waiting for AI analysis...';
    // } else {
    //     streamImage.style.display = 'none';
    //     streamPlaceholder.style.display = 'block';
    //     streamImage.src = '';
    // }
}



function startStream2() {


    // const initialQuery = window.initialQuery || "";
    // const commandOutput = window.commandOutput || "";
    
    const prompt = "give screen analysis";
    // if (!prompt) {
    //     statusMessage.textContent = 'Please enter a prompt before starting';
    //     return;
    // }

    // Disable UI during request
    startBtn.disabled = true;
    // statusMessage.textContent = 'Starting stream...';

    fetch('/start_stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Start the stream
                // streamImage.src = '/stream';
                updateUIState(true);

                // Start polling for responses
                responseInterval = setInterval(fetchResponse2, 1000);
                statusMessage.textContent = data.message;
                statusMessage.style.color='#10b981'
            } else {
                // Handle error
                statusMessage.textContent = data.message;
                startBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            statusMessage.textContent = 'Error starting stream';
            startBtn.disabled = false;
        });
}


function fetchResponse2() {
    if (!isStreaming) return;

    fetch('/get_gemini_response')
        .then(response => response.json())
        .then(data => {
            if (data.response) {
                // console.log(data)
                // console.log(data.response)
                document.getElementById("analysis-results").classList.remove('hidden');
                document.getElementById("analysis-summary-stream").innerHTML = marked.parse(data.response.summary)
                // console.log(data.response.summary)
                // window.vison_stop_agent=data.response.vison_stop_agent
                window.summary_vision = data.response.summary
                console.log(data.response.vison_stop_agent)
                // if(data.response.vison_stop_agent=='True' || data.response.vison_stop_agent==true)
                // {
                //     stopStream()
                // }
            }
        })
        .catch(error => {
            console.error('Error fetching response:', error);
        });
}




function startStream() {


    const initialQuery = window.initialQuery || "";
    const commandOutput = window.commandOutput || "";
    
    const prompt = "initial query: \n" + initialQuery + "\n Command output:\n" + commandOutput + "\n\n";
    // if (!prompt) {
    //     statusMessage.textContent = 'Please enter a prompt before starting';
    //     return;
    // }

    // Disable UI during request
    startBtn.disabled = true;
    // statusMessage.textContent = 'Starting stream...';

    fetch('/start_stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Start the stream
                // streamImage.src = '/stream';
                updateUIState(true);

                // Start polling for responses
                responseInterval = setInterval(fetchResponse, 1000);
                statusMessage.textContent = data.message;
                statusMessage.style.color='#10b981'
            } else {
                // Handle error
                statusMessage.textContent = data.message;
                startBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            statusMessage.textContent = 'Error starting stream';
            startBtn.disabled = false;
        });
}

function stopStream() {
    // Disable UI during request
    stopBtn.disabled = true;
    statusMessage.textContent = 'Stopping stream...';

    fetch('/stop_stream', {
        method: 'POST',
    })
        .then(response => response.json())
        .then(data => {
            // Clear response interval
            if (responseInterval) {
                clearInterval(responseInterval);
                responseInterval = null;
            }
            updateUIState(false);
            statusMessage.textContent = data.message;
            statusMessage.style.color='red'
            setTimeout(speakTextFromDiv(),3000)
        })
        .catch(error => {
            console.error('Error:', error);
            statusMessage.textContent = 'Error stopping stream';
            stopBtn.disabled = false;
            setTimeout(speakTextFromDiv(),1000)
        });
}

function fetchResponse() {
    if (!isStreaming) return;

    fetch('/get_gemini_response')
        .then(response => response.json())
        .then(data => {
            if (data.response) {
                // console.log(data)
                // console.log(data.response)
                document.getElementById("analysis-results").classList.remove('hidden');
                document.getElementById("analysis-summary-stream").innerHTML = marked.parse(data.response.summary)
                // console.log(data.response.summary)
                window.vison_stop_agent=data.response.vison_stop_agent
                window.summary_vision = data.response.summary
                console.log(data.response.vison_stop_agent)
                if(data.response.vison_stop_agent=='True' || data.response.vison_stop_agent==true)
                {
                    stopStream()
                }
            }
        })
        .catch(error => {
            console.error('Error fetching response:', error);
        });
}

function speakTextFromDiv(divId) {
    // Get the div element
    const div = document.getElementById("analysis-summary-stream");
    
    // Check if div exists
    if (!div) {
        console.error(`Div with ID "${divId}" not found`);
        return;
    }
    
    // Get text from the div
    const textToSpeak = div.innerText || div.textContent;
    
    // Check if there's text to speak
    if (!textToSpeak || textToSpeak.trim() === '') {
        console.warn('No text to speak found in the div');
        return;
    }
    
    // Send the text to the server
    fetch('/speak', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message_to_speak: textToSpeak
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        console.log('Text sent for speaking');
    })
    .catch(error => {
        console.error('Error sending text to speak:', error);
    });
}
// Event listeners
startBtn.addEventListener('click', startStream2);
stopBtn.addEventListener('click', stopStream);

// Handle stream image errors
// streamImage.addEventListener('error', function (e) {
//     if (isStreaming) {
//         statusMessage.textContent = 'Stream connection lost. Please stop and restart.';
//     }
// });

// Initialize UI
updateUIState(false);