/**
 * Presenter view functionality for ClassPulse
 * Simplified and more robust version
 */

console.log("PRESENTER.JS LOADED - NEW VERSION");

let socket;
let activeQuestionId = null;
let chartInstances = {};

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Presenter');
    console.log('Presenter view initialized');
    console.log('Session ID:', sessionId);
    
    // Add click handlers to questions immediately
    const questionItems = document.querySelectorAll('.question-item');
    console.log(`Found ${questionItems.length} question items`);
    
    // Add click handlers in multiple ways for redundancy
    questionItems.forEach(item => {
        console.log('Setting up click handler for question item:', item.dataset.id);
        
        // Method 1: Standard click event listener
        item.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const questionId = this.dataset.id;
            console.log('Question clicked:', questionId);
            
            // Update UI to show this question is active
            document.querySelectorAll('.question-item').forEach(q => q.classList.remove('active'));
            this.classList.add('active');
            
            // Activate the question
            activateQuestion(questionId);
        });
        
        // Method 2: Using jQuery as fallback (if jQuery is available)
        if (typeof $ !== 'undefined') {
            $(item).on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                const questionId = this.dataset.id;
                console.log('Question clicked (jQuery):', questionId);
                activateQuestion(questionId);
            });
        }
        
        // Add a more obvious visual style to indicate it's clickable
        item.style.cursor = 'pointer';
        item.style.position = 'relative';
        
        // Add an action hint for better UX
        const hint = document.createElement('div');
        hint.textContent = 'Click to activate';
        hint.style.position = 'absolute';
        hint.style.top = '5px';
        hint.style.right = '10px';
        hint.style.fontSize = '10px';
        hint.style.color = '#6366F1';
        hint.style.fontWeight = 'bold';
        item.appendChild(hint);
    });
    
    // Add a fallback button for each question
    questionItems.forEach(item => {
        const questionId = item.dataset.id;
        const activateBtn = document.createElement('button');
        activateBtn.textContent = 'Activate';
        activateBtn.className = 'bg-blue-500 hover:bg-blue-600 text-white py-1 px-2 text-xs rounded ml-2';
        activateBtn.style.fontSize = '0.7rem';
        activateBtn.style.marginLeft = 'auto';
        
        activateBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Activate button clicked for question:', questionId);
            
            // Update UI to show this question is active
            document.querySelectorAll('.question-item').forEach(q => q.classList.remove('active'));
            item.classList.add('active');
            
            // Activate the question
            activateQuestion(questionId);
        });
        
        // Temporary disabled as we have form buttons already
        // item.appendChild(activateBtn);
    });
    
    // Initialize Socket.IO connection
    initializeSocketConnection();
    
    // Add a global click handler to catch and log all clicks
    document.addEventListener('click', function(e) {
        const target = e.target;
        const isQuestionItem = target.closest('.question-item');
        if (isQuestionItem) {
            console.log('Global click handler caught click on question item');
        }
    });
});

function initializeSocketConnection() {
    console.log('Attempting to initialize Socket.IO connection...');
    // Connect to Socket.IO server with explicit configuration
    try {
        console.log('Connecting to Socket.IO server...');
        socket = io.connect(window.location.origin, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });
        
        // Socket connection handlers
        socket.on('connect', function() {
    console.log('Socket.IO connected successfully');
            console.log('Connected to server as presenter ✅');
            
            // Join the session room
            socket.emit('presenter_connected', {
                session_id: sessionId
            });
            
            console.log('Joined session room:', 'session_' + sessionId);
            
            // Add a visual indicator that we're connected
            const indicator = document.createElement('div');
            indicator.textContent = 'Connected ✅';
            indicator.style.position = 'fixed';
            indicator.style.top = '10px';
            indicator.style.right = '10px';
            indicator.style.backgroundColor = '#4CAF50';
            indicator.style.color = 'white';
            indicator.style.padding = '5px 10px';
            indicator.style.borderRadius = '3px';
            indicator.style.zIndex = '9999';
            document.body.appendChild(indicator);
            
            setTimeout(() => {
                indicator.style.opacity = '0';
                indicator.style.transition = 'opacity 1s';
            }, 3000);
        });
        
        socket.on('connect_error', function(error) {
    console.error('Socket.IO connection error:', error);
            console.error('Connection error:', error);
        });
        
        socket.on('disconnect', function() {
    console.log('Socket.IO disconnected');
            console.log('Disconnected from server ❌');
        });
        
        // Handle incoming response data
        socket.on('response_update', function(data) {
            console.log('Response update received:', data);
            handleResponseUpdate(data);
            
            // Display a notification to the presenter with the count
            if (data.responses && data.responses.length > 0) {
                const count = data.responses.length;
                const notification = document.createElement('div');
                notification.textContent = `${count} ${count === 1 ? 'response' : 'responses'} received`;
                notification.style.position = 'fixed';
                notification.style.top = '10px';
                notification.style.right = '10px';
                notification.style.backgroundColor = 'rgba(76, 175, 80, 0.9)';
                notification.style.color = 'white';
                notification.style.padding = '5px 10px';
                notification.style.borderRadius = '3px';
                notification.style.zIndex = '9999';
                document.body.appendChild(notification);
                
                setTimeout(() => {
                    notification.style.opacity = '0';
                    notification.style.transition = 'opacity 0.5s';
                    setTimeout(() => document.body.removeChild(notification), 500);
                }, 1500);
            }
        });
        
        // Handle response to question activation
        socket.on('question_activated', function(data) {
            console.log('Question activation confirmed:', data);
        });
    } catch (e) {
        console.error('Socket initialization error:', e);
    }
}

function activateQuestion(questionId) {
    console.log('Activating question:', questionId);
    
    // Hide "no question active" message
    const noQuestionActive = document.querySelector('.no-question-active');
    if (noQuestionActive) noQuestionActive.style.display = 'none';
    
    // Show question display
    const questionDisplay = document.querySelector('.question-display');
    if (questionDisplay) questionDisplay.style.display = 'block';
    
    // Set as active question
    activeQuestionId = questionId;
    
    // Update the question text display
    const questionItem = document.querySelector(`.question-item[data-id="${questionId}"]`);
    if (questionItem) {
        const questionText = questionItem.querySelector('p').textContent;
        const questionType = questionItem.querySelector('.question-type').textContent;
        
        // Update all question items to show which is active
        document.querySelectorAll('.question-item').forEach(item => {
            item.classList.remove('active');
        });
        questionItem.classList.add('active');
        
        // Update active question text
        const activeQuestionText = document.getElementById('active-question-text');
        if (activeQuestionText) {
            activeQuestionText.textContent = questionText;
            console.log('Updated question text to:', questionText);
        }
        
        // Reset UI
        const responseCount = document.getElementById('response-count');
        if (responseCount) responseCount.textContent = '0';
        
        // Clear any previous visualizations
        const chartContainer = document.getElementById('chart-container');
        const wordCloudContainer = document.getElementById('word-cloud-container');
        const ratingScaleContainer = document.getElementById('rating-scale-container');
        
        if (chartContainer) chartContainer.innerHTML = '';
        if (wordCloudContainer) wordCloudContainer.innerHTML = '';
        if (ratingScaleContainer) ratingScaleContainer.innerHTML = '';
        
        // Show appropriate visualization container based on question type
        if (questionType.toLowerCase().includes('multiple choice')) {
            if (chartContainer) chartContainer.style.display = 'block';
            if (wordCloudContainer) wordCloudContainer.style.display = 'none';
            if (ratingScaleContainer) ratingScaleContainer.style.display = 'none';
        } else if (questionType.toLowerCase().includes('word cloud')) {
            if (chartContainer) chartContainer.style.display = 'none';
            if (wordCloudContainer) wordCloudContainer.style.display = 'block';
            if (ratingScaleContainer) ratingScaleContainer.style.display = 'none';
        } else if (questionType.toLowerCase().includes('rating')) {
            if (chartContainer) chartContainer.style.display = 'none';
            if (wordCloudContainer) wordCloudContainer.style.display = 'none';
            if (ratingScaleContainer) ratingScaleContainer.style.display = 'block';
        }
    } else {
        console.error('Question item not found in DOM for ID:', questionId);
    }
    
    // Try to activate the question using both methods for redundancy:
    // 1. First try Socket.IO if connected
    if (socket && socket.connected) {
        console.log('Emitting activate_question event via Socket.IO for question ID:', questionId);
        
        socket.emit('activate_question', {
            question_id: questionId,
            session_id: sessionId
        });
    }
    
    // 2. Always also use HTTP API as a fallback/redundant method
    console.log('Using HTTP API as fallback to activate question ID:', questionId);
    
    // Make a POST request to activate the question
    // Add the X-Requested-With header to indicate this is an AJAX request
    fetch(`/api/activate_question/${questionId}/${sessionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'  // This tells the server to return JSON instead of redirecting
        }
    })
    .then(response => {
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        } else {
            // If not JSON, it's probably a redirect or HTML - consider it a success
            console.log('Non-JSON response received, activation likely succeeded');
            return { success: true, message: 'Activation request processed' };
        }
    })
    .then(data => {
        console.log('Question activation API response:', data);
        if (data.success) {
            console.log('Question activated successfully via HTTP API');
        }
    })
    .catch(error => {
        console.error('Error activating question via HTTP API:', error);
        // Even if there's an error with the fetch, the socket.io activation might have worked
        console.log('Continuing with socket.io activation as backup');
    });
    
    // Show visual feedback regardless of activation method
    const feedback = document.createElement('div');
    feedback.textContent = 'Question activated!';
    feedback.style.position = 'fixed';
    feedback.style.top = '50%';
    feedback.style.left = '50%';
    feedback.style.transform = 'translate(-50%, -50%)';
    feedback.style.backgroundColor = 'rgba(76, 175, 80, 0.9)';
    feedback.style.color = 'white';
    feedback.style.padding = '20px';
    feedback.style.borderRadius = '5px';
    feedback.style.zIndex = '9999';
    feedback.style.fontWeight = 'bold';
    document.body.appendChild(feedback);
    
    setTimeout(() => {
        feedback.style.opacity = '0';
        feedback.style.transition = 'opacity 0.5s';
        setTimeout(() => document.body.removeChild(feedback), 500);
    }, 1500);
}

function handleResponseUpdate(data) {
    console.log('Response update received:', data);
    
    if (!data || data.question_id != activeQuestionId) {
        console.log('Ignoring response update for inactive question:', data ? data.question_id : 'unknown');
        return;
    }
    
    // Update response count
    const responseCount = document.getElementById('response-count');
    if (responseCount) {
        responseCount.textContent = data.responses.length;
        console.log('Updated response count to:', data.responses.length);
    }
    
    // Get active question type
    const activeQuestion = document.querySelector(`.question-item[data-id="${activeQuestionId}"]`);
    if (!activeQuestion) {
        console.error('Active question element not found in DOM');
        return;
    }
    
    const questionType = activeQuestion.querySelector('.question-type').textContent.toLowerCase();
    console.log('Active question type:', questionType);
    
    // Ensure question display is visible
    const noQuestionActive = document.querySelector('.no-question-active');
    const questionDisplay = document.querySelector('.question-display');
    if (noQuestionActive) noQuestionActive.style.display = 'none';
    if (questionDisplay) questionDisplay.style.display = 'block';
    
    // Update visualization based on question type
    if (questionType.includes('multiple choice')) {
        console.log('Updating multiple choice chart with', data.responses.length, 'responses');
        updateMultipleChoiceChart(data.responses);
    } else if (questionType.includes('word cloud')) {
        console.log('Updating word cloud with', data.responses.length, 'responses');
        updateWordCloud(data.responses);
    } else if (questionType.includes('rating')) {
        console.log('Updating rating scale chart with', data.responses.length, 'responses');
        updateRatingScaleChart(data.responses);
    } else {
        console.warn('Unknown question type:', questionType);
    }
}

function updateMultipleChoiceChart(responses) {
    console.log('updateMultipleChoiceChart called with', responses.length, 'responses');
    
    // Create a debug div to show raw responses
    const debugDiv = document.createElement('div');
    debugDiv.style.marginTop = '20px';
    debugDiv.style.padding = '10px';
    debugDiv.style.border = '1px solid #ccc';
    debugDiv.style.backgroundColor = '#f8f8f8';
    debugDiv.style.fontSize = '12px';
    debugDiv.style.fontFamily = 'monospace';
    
    debugDiv.innerHTML = `<strong>Debug - Raw Responses (${responses.length}):</strong><br>`;
    responses.forEach(r => {
        debugDiv.innerHTML += `• ${r.participant_id.substr(0,8)}: "${r.value}"<br>`;
    });
    
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer) {
        console.error('Chart container not found');
        return;
    }
    
    // Clear previous content
    chartContainer.innerHTML = '';
    
    // Add the debug info
    chartContainer.appendChild(debugDiv);
    
    chartContainer.style.display = 'block';
    
    // Hide other containers
    const wordCloudContainer = document.getElementById('word-cloud-container');
    const ratingScaleContainer = document.getElementById('rating-scale-container');
    
    if (wordCloudContainer) wordCloudContainer.style.display = 'none';
    if (ratingScaleContainer) ratingScaleContainer.style.display = 'none';
    
    // Get the question to access its options
    const questionItem = document.querySelector(`.question-item[data-id="${activeQuestionId}"]`);
    if (!questionItem) return;
    
    // Try to get options from the question element
    let options = [];
    try {
        const optionsData = questionItem.dataset.options;
        if (optionsData) {
            options = JSON.parse(optionsData);
        }
    } catch (e) {
        console.error('Error parsing options:', e);
    }
    
    // If no options found, extract them from responses
    if (!options || !options.length) {
        const uniqueResponses = new Set();
        responses.forEach(response => {
            if (response.value) uniqueResponses.add(response.value);
        });
        options = Array.from(uniqueResponses);
    }
    
    // Count responses for each option
    const counts = {};
    options.forEach(option => {
        counts[option] = 0;
    });
    
    responses.forEach(response => {
        if (counts[response.value] !== undefined) {
            counts[response.value]++;
        }
    });
    
    // Prepare chart data
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    
    // Generate colors
    const backgroundColors = generateColors(labels.length);
    
    // Create or update chart
    if (!chartContainer.querySelector('canvas')) {
        const canvas = document.createElement('canvas');
        chartContainer.appendChild(canvas);
    }
    
    const ctx = chartContainer.querySelector('canvas').getContext('2d');
    
    // Destroy existing chart if it exists
    if (chartInstances.multipleChoice) {
        chartInstances.multipleChoice.destroy();
    }
    
    // Create new chart
    chartInstances.multipleChoice = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Responses',
                data: data,
                backgroundColor: backgroundColors,
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

function updateWordCloud(responses) {
    const wordCloudContainer = document.getElementById('word-cloud-container');
    if (!wordCloudContainer) return;
    
    wordCloudContainer.style.display = 'block';
    document.getElementById('chart-container').style.display = 'none';
    document.getElementById('rating-scale-container').style.display = 'none';
    
    // Clear previous word cloud
    wordCloudContainer.innerHTML = '';
    
    // Process words
    const words = {};
    responses.forEach(response => {
        // Split into words, clean, and count
        const text = response.value.toLowerCase().trim();
        if (text) {
            if (words[text]) {
                words[text]++;
            } else {
                words[text] = 1;
            }
        }
    });
    
    // Convert to array for rendering
    const wordEntries = Object.entries(words);
    
    if (wordEntries.length === 0) {
        const emptyMsg = document.createElement('p');
        emptyMsg.textContent = 'No responses yet';
        emptyMsg.className = 'text-center text-gray-500 mt-10';
        wordCloudContainer.appendChild(emptyMsg);
        return;
    }
    
    const maxCount = Math.max(...wordEntries.map(([_, count]) => count));
    
    // Create simple word cloud
    const cloudDiv = document.createElement('div');
    cloudDiv.className = 'word-cloud-visualization p-4 flex flex-wrap justify-center';
    
    wordEntries.sort((a, b) => b[1] - a[1]).forEach(([word, count]) => {
        const size = 1 + (count / maxCount) * 2.5; // Scale between 1-3.5em
        const span = document.createElement('span');
        span.textContent = word;
        span.style.fontSize = `${size}em`;
        span.style.padding = '0.5em';
        span.style.color = getRandomColor();
        span.style.fontWeight = 'bold';
        cloudDiv.appendChild(span);
    });
    
    wordCloudContainer.appendChild(cloudDiv);
}

function updateRatingScaleChart(responses) {
    const scaleContainer = document.getElementById('rating-scale-container');
    if (!scaleContainer) return;
    
    scaleContainer.style.display = 'block';
    document.getElementById('chart-container').style.display = 'none';
    document.getElementById('word-cloud-container').style.display = 'none';
    
    // Default scale from 1-5
    const min = 1;
    const max = 5;
    
    // Create labels for each value in the scale
    const labels = [];
    for (let i = min; i <= max; i++) {
        labels.push(i.toString());
    }
    
    // Count responses for each value
    const counts = {};
    labels.forEach(label => {
        counts[label] = 0;
    });
    
    responses.forEach(response => {
        const value = response.value.toString();
        if (counts[value] !== undefined) {
            counts[value]++;
        }
    });
    
    // Prepare chart data
    const data = labels.map(label => counts[label]);
    
    // Create or update chart
    if (!scaleContainer.querySelector('canvas')) {
        const canvas = document.createElement('canvas');
        scaleContainer.appendChild(canvas);
    }
    
    // Generate gradient colors based on value
    const backgroundColors = labels.map((_, index) => {
        const value = (index / (labels.length - 1)) * 255;
        return `rgba(${value}, ${150}, ${255 - value}, 0.7)`;
    });
    
    const ctx = scaleContainer.querySelector('canvas').getContext('2d');
    
    // Destroy existing chart if it exists
    if (chartInstances.ratingScale) {
        chartInstances.ratingScale.destroy();
    }
    
    chartInstances.ratingScale = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Responses',
                data: data,
                backgroundColor: backgroundColors,
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

// Helper functions
function generateColors(count) {
    const colors = [
        'rgba(59, 130, 246, 0.7)',   // Blue
        'rgba(16, 185, 129, 0.7)',   // Green
        'rgba(245, 158, 11, 0.7)',   // Yellow
        'rgba(239, 68, 68, 0.7)',    // Red
        'rgba(139, 92, 246, 0.7)',   // Purple
        'rgba(236, 72, 153, 0.7)',   // Pink
        'rgba(14, 165, 233, 0.7)',   // Light Blue
        'rgba(249, 115, 22, 0.7)',   // Orange
        'rgba(20, 184, 166, 0.7)',   // Teal
    ];
    
    // If we need more colors than are predefined, generate random ones
    if (count > colors.length) {
        for (let i = colors.length; i < count; i++) {
            colors.push(getRandomColor(0.7));
        }
    }
    
    return colors.slice(0, count);
}

function getRandomColor(alpha = 0.7) {
    const r = Math.floor(Math.random() * 200) + 55;
    const g = Math.floor(Math.random() * 200) + 55;
    const b = Math.floor(Math.random() * 200) + 55;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}