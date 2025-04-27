/**
 * Audience view functionality for ClassPulse
 * Simplified and more robust version
 */

console.log("*** Audience view script started ***");

let socket;
let currentQuestion = null;

console.log('**** Audience view initialized ****');
console.log('Session ID:', sessionId);
console.log('Participant ID:', participantId);

// Add a debug button to force show the active question (helpful for troubleshooting)
const debugButton = document.createElement('button');
debugButton.textContent = 'Debug: Force Show Active Question';
debugButton.style.position = 'fixed';
debugButton.style.bottom = '10px';
debugButton.style.right = '10px';
debugButton.style.zIndex = '9999';
debugButton.style.padding = '5px';
debugButton.style.fontSize = '10px';
debugButton.style.backgroundColor = '#f0f0f0';
debugButton.style.border = '1px solid #ccc';
debugButton.addEventListener('click', function() {
    console.log('Debug button clicked');
    if (currentQuestion) {
        console.log('Force showing current question:', currentQuestion);
        updateQuestionUI(currentQuestion);
    } else if (typeof activeQuestion !== 'undefined' && activeQuestion) {
        console.log('Force showing active question:', activeQuestion);
        currentQuestion = activeQuestion;
        updateQuestionUI(activeQuestion);
    } else {
        alert('No active question available');
    }
});
document.body.appendChild(debugButton);

// Check if we have an active question already
if (typeof activeQuestion !== 'undefined' && activeQuestion) {
    console.log('Found active question on page load:', activeQuestion);
    currentQuestion = activeQuestion;

    // Explicitly call updateQuestionUI to show the question
    setTimeout(function() {
        console.log('Showing active question after timeout');
        updateQuestionUI(activeQuestion);
    }, 500);
} else {
    console.log('No active question found on page load');
    showNotification('Waiting for the presenter to activate a question...', 'info');
}

// Initialize Socket.IO connection
initializeSocketConnection();

// Set up form submission handlers
setupResponseSubmission();


function initializeSocketConnection() {
    try {
        console.log('Connecting to Socket.IO server...');

        // Connect to Socket.IO server with explicit configuration
        socket = io.connect(window.location.origin, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 10,
            timeout: 20000,
            transports: ['websocket', 'polling'] // Try WebSocket first, fallback to polling
        });

        // Socket connection handlers
        socket.on('connect', function() {
            console.log('Connected to session as audience member ✅');

            // Update UI to show connected status
            updateConnectionStatus(true);

            // Join rooms by both ID and code for redundancy
            joinRooms();

            // Add a visual indicator that we're connected
            showNotification('Connected to session', 'success');

            // If we have a current question stored, request it again to ensure we're in sync
            if (currentQuestion && currentQuestion.id) {
                socket.emit('request_active_question', {
                    session_id: sessionId,
                    session_code: sessionCode
                });
            }
        });

        socket.on('connect_error', function(error) {
            console.error('Connection error:', error);
            updateConnectionStatus(false);

            // Auto-retry connection with exponential backoff
            setTimeout(() => {
                console.log('Attempting to reconnect...');
                socket.connect();
            }, 2000);
        });

        socket.on('disconnect', function(reason) {
            console.log(`Disconnected from server (${reason}) ❌`);
            updateConnectionStatus(false);

            // If the disconnect was not initiated by the client, attempt to reconnect
            if (reason !== 'io client disconnect') {
                showNotification('Connection lost. Attempting to reconnect...', 'error');
            }
        });

        // Handle room join confirmation
        socket.on('room_joined', function(data) {
            console.log('Room join confirmed:', data);
            showNotification('Joined session room', 'success');
        });

        // Handle receiving question activation from presenter
        socket.on('question_activated', function(data) {
            console.log('Question activated event received:', data);

            // Show a notification that a question was activated
            showNotification('New question activated!', 'info');

            // If we don't receive question_details within 1 second, request them
            setTimeout(() => {
                if (!currentQuestion || currentQuestion.id != data.question_id) {
                    console.log('Question details not received, requesting them...');
                    socket.emit('request_question_details', {
                        question_id: data.question_id,
                        session_id: sessionId
                    });
                }
            }, 1000);
        });

        // Handle receiving question details
        socket.on('question_details', function(data) {
            console.log('Question details received:', data);

            // Store the current question
            currentQuestion = data;

            // Update UI with the question
            updateQuestionUI(data);
        });

        // Handle response confirmation
        socket.on('response_received', function(data) {
            console.log('Response received confirmation:', data);

            // Only show if this was our response
            if (data.participant_id === participantId) {
                showResponseConfirmation();
            }
        });

        // Setup a heartbeat to keep the connection alive
        setInterval(() => {
            if (socket.connected) {
                socket.emit('heartbeat', { participant_id: participantId });
            }
        }, 30000);
    } catch (e) {
        console.error('Socket initialization error:', e);
        // Show a more visible error to the user
        showNotification('Connection error. Please refresh the page.', 'error');
    }
}

function joinRooms() {
    // Join room by session ID
    const roomById = `session_${sessionId}`;
    socket.emit('join_room', { room: roomById });
    console.log('Joining room by ID:', roomById);

    // Join room by session code
    const roomByCode = `code_${sessionCode}`;
    socket.emit('join_room', { room: roomByCode });
    console.log('Joining room by code:', roomByCode);
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connection-status');
    if (statusIndicator) {
        if (connected) {
            statusIndicator.textContent = 'Connected';
            statusIndicator.classList.remove('disconnected');
            statusIndicator.classList.add('connected');
        } else {
            statusIndicator.textContent = 'Disconnected';
            statusIndicator.classList.remove('connected');
            statusIndicator.classList.add('disconnected');
        }
    }
}

function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.left = '50%';
    notification.style.transform = 'translateX(-50%)';

    // Set styles based on notification type
    if (type === 'success') {
        notification.style.backgroundColor = '#4CAF50';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#F44336';
    } else {
        notification.style.backgroundColor = '#2196F3';
    }

    notification.style.color = 'white';
    notification.style.padding = '10px 20px';
    notification.style.borderRadius = '5px';
    notification.style.zIndex = '1000';
    document.body.appendChild(notification);

    // Remove after animation
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.5s';
        setTimeout(() => document.body.removeChild(notification), 500);
    }, 3000);
}

function updateQuestionUI(question) {
    // For debugging - show the question in the console
    console.log('Updating question UI with:', question);

    // Show a notification to inform the user
    showNotification('Question received: ' + question.text, 'info');

    // Hide waiting message and show question container
    const waitingMessage = document.getElementById('waiting-message');
    if (waitingMessage) {
        console.log('Hiding waiting message');
        waitingMessage.style.display = 'none';
    }

    // Get the question container
    const questionContainer = document.getElementById('question-container');
    if (!questionContainer) {
        console.error('Question container not found');
        alert('Question container not found on page. Please refresh or contact support.');
        return;
    }

    // IMPORTANT: Explicitly show the question container
    console.log('Showing question container');
    questionContainer.style.display = 'block';

    // Display question text
    const questionText = document.getElementById('question-text');
    if (questionText) {
        questionText.textContent = question.text;
        console.log('Updated question text to:', question.text);
    } else {
        console.error('Question text element not found');
    }

    // Hide all question type containers first
    const allContainers = document.querySelectorAll('.question-type-container');
    allContainers.forEach(container => {
        container.style.display = 'none';
    });

    // Hide any previous response confirmation
    const responseConfirmation = document.getElementById('response-confirmation');
    if (responseConfirmation) {
        responseConfirmation.style.display = 'none';
    }

    // Show the appropriate container based on question type
    let formContainer;

    if (question.type === 'multiple_choice') {
        formContainer = document.getElementById('multiple-choice-container');
        if (formContainer) {
            formContainer.style.display = 'block';
            // Create radio buttons for options
            const optionsContainer = formContainer.querySelector('.options-container');
            if (optionsContainer) {
                optionsContainer.innerHTML = '';

                if (question.options && question.options.length) {
                    question.options.forEach((option, index) => {
                        const label = document.createElement('label');
                        label.className = 'option-item';

                        const input = document.createElement('input');
                        input.type = 'radio';
                        input.name = 'mc-option';
                        input.value = option;
                        input.id = `option-${index}`;
                        input.required = true;

                        const span = document.createElement('span');
                        span.textContent = option;

                        label.appendChild(input);
                        label.appendChild(span);
                        optionsContainer.appendChild(label);
                    });
                } else {
                    optionsContainer.innerHTML = '<div class="text-red-500">No options available for this question.</div>';
                }
            }
        }
    } else if (question.type === 'word_cloud') {
        formContainer = document.getElementById('word-cloud-container');
        if (formContainer) {
            formContainer.style.display = 'block';
            // Clear the input
            const input = formContainer.querySelector('input[type="text"]');
            if (input) {
                input.value = '';
            }
        }
    } else if (question.type === 'rating_scale') {
        formContainer = document.getElementById('rating-scale-container');
        if (formContainer) {
            formContainer.style.display = 'block';

            // Set up the rating scale
            const options = question.options || { min: 1, max: 5 };
            const min = parseInt(options.min) || 1;
            const max = parseInt(options.max) || 5;

            const rangeInput = formContainer.querySelector('input[type="range"]');
            if (rangeInput) {
                rangeInput.min = min;
                rangeInput.max = max;
                rangeInput.value = Math.floor((max + min) / 2); // Start in the middle

                // Update the display value
                const displayValue = formContainer.querySelector('.rating-value');
                if (displayValue) {
                    displayValue.textContent = rangeInput.value;
                }

                // Add event listener to update display value when slider moves
                rangeInput.addEventListener('input', function() {
                    if (displayValue) {
                        displayValue.textContent = this.value;
                    }
                });
            }
        }
    }

    // Show the question container
    questionContainer.style.display = 'block';

    // Hide the waiting message
    const waitingMsgElement = document.getElementById('waiting-message');
    if (waitingMsgElement) {
        waitingMsgElement.style.display = 'none';
    }
}

function setupResponseSubmission() {
    console.log("Setting up response submission handlers");

    // Important: Ensure all forms use AJAX submission, not traditional form submission

    // Multiple Choice form
    const mcForm = document.getElementById('multiple-choice-form');
    if (mcForm) {
        console.log("Found multiple choice form, adding submit handler");

        // Remove any action attribute that might cause a page redirect
        mcForm.removeAttribute('action');
        mcForm.removeAttribute('method');

        mcForm.onsubmit = function(e) {
            // Very important: prevent the default form submission
            e.preventDefault();
            console.log("Multiple choice form submitted");

            // Get selected option
            const selectedOption = mcForm.querySelector('input[name="mc-option"]:checked');
            if (!selectedOption) {
                alert('Please select an option');
                return false;
            }

            console.log("Selected option:", selectedOption.value);
            submitResponse(selectedOption.value);

            // Return false to prevent traditional form submission
            return false;
        };
        console.log("Successfully assigned onsubmit handler to multiple-choice-form");
    } else {
        console.warn("Multiple choice form not found");
    }

    // Word Cloud form
    const wcForm = document.getElementById('word-cloud-form');
    if (wcForm) {
        console.log("Found word cloud form, adding submit handler");

        // Remove any action attribute that might cause a page redirect
        wcForm.removeAttribute('action');
        wcForm.removeAttribute('method');

        wcForm.onsubmit = function(e) {
            // Very important: prevent the default form submission
            e.preventDefault();
            console.log("Word cloud form submitted");

            // Get entered text
            const textInput = wcForm.querySelector('input[type="text"]');
            if (!textInput || !textInput.value.trim()) {
                alert('Please enter a word or phrase');
                return false;
            }

            console.log("Text input:", textInput.value.trim());
            submitResponse(textInput.value.trim());

            // Return false to prevent traditional form submission
            return false;
        };
    }

    // Rating Scale form
    const ratingForm = document.getElementById('rating-scale-form');
    if (ratingForm) {
        console.log("Found rating scale form, adding submit handler");

        // Remove any action attribute that might cause a page redirect
        ratingForm.removeAttribute('action');
        ratingForm.removeAttribute('method');

        ratingForm.onsubmit = function(e) {
            // Very important: prevent the default form submission
            e.preventDefault();
            console.log("Rating scale form submitted");

            // Get selected rating
            const ratingInput = ratingForm.querySelector('input[type="range"]');
            if (!ratingInput) {
                alert('Please select a rating');
                return false;
            }

            console.log("Rating input:", ratingInput.value);
            submitResponse(ratingInput.value);

            // Return false to prevent traditional form submission
            return false;
        };
    }

    // Add a click listener to document to capture any submit events that might bubble up
    document.addEventListener('click', function(e) {
        if (e.target && e.target.tagName === 'BUTTON' && e.target.type === 'submit') {
            console.log("Submit button clicked:", e.target);

            // Find the parent form
            const form = e.target.closest('form');
            if (form) {
                console.log("Parent form found:", form.id);

                // Validate and submit based on form type
                if (form.id === 'multiple-choice-form') {
                    const selectedOption = form.querySelector('input[name="mc-option"]:checked');
                    if (selectedOption) {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log("Selected option:", selectedOption.value);
                        submitResponse(selectedOption.value);
                    }
                }
            }
        }
    });
}

function submitResponse(value) {
    console.log(`submitResponse called with value: ${value}`);

    // Ensure we have an active question
    if (!currentQuestion) {
        console.error('No active question');
        alert('There is no active question.');
        return;
    }

    console.log('Submitting response:', value, 'for question ID:', currentQuestion.id);

    // Send the response to the server
    if (socket && socket.connected) {
        // Show a submitting indicator
        showNotification('Submitting your response...', 'info');

        socket.emit('submit_response', {
            question_id: currentQuestion.id,
            session_id: sessionId,
            value: value
        });

        // Set a fallback in case we don't get a response confirmation
        setTimeout(() => {
            // Assume success if no confirmation received within 3 seconds
            console.log('Response confirmation timeout - showing success anyway');
            showResponseConfirmation();
        }, 3000);
    } else {
        console.error('Socket not connected. Cannot submit response.');
        alert('Connection to server lost. Please refresh the page and try again.');
    }

    // Return true to indicate success (helps with form submission)
    return true;
}

function showResponseConfirmation() {
    // Add debug info
    console.log('showResponseConfirmation called');

    // Hide all forms
    const allForms = document.querySelectorAll('.question-type-container');
    allForms.forEach(form => {
        form.style.display = 'none';
    });

    // Show confirmation message
    const confirmation = document.getElementById('response-confirmation');
    if (confirmation) {
        confirmation.style.display = 'block';
        confirmation.classList.add('animate-confirmation');

        // Show success message
        showNotification('Response submitted successfully!', 'success');

        // Create a larger, more visible confirmation popup
        const largeConfirmation = document.createElement('div');
        largeConfirmation.textContent = 'Response Submitted!';
        largeConfirmation.style.position = 'fixed';
        largeConfirmation.style.top = '50%';
        largeConfirmation.style.left = '50%';
        largeConfirmation.style.transform = 'translate(-50%, -50%)';
        largeConfirmation.style.backgroundColor = 'rgba(76, 175, 80, 0.9)';
        largeConfirmation.style.color = 'white';
        largeConfirmation.style.padding = '30px 50px';
        largeConfirmation.style.borderRadius = '10px';
        largeConfirmation.style.zIndex = '9999';
        largeConfirmation.style.fontWeight = 'bold';
        largeConfirmation.style.fontSize = '24px';
        largeConfirmation.style.textAlign = 'center';
        document.body.appendChild(largeConfirmation);

        setTimeout(() => {
            largeConfirmation.style.opacity = '0';
            largeConfirmation.style.transition = 'opacity 0.5s';
            setTimeout(() => document.body.removeChild(largeConfirmation), 500);
        }, 2000);
    } else {
        console.error('Response confirmation element not found');
    }
}
