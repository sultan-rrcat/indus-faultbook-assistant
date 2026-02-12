// ===============================
// 🌙 Theme Management
// ===============================
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const savedTheme = localStorage.getItem('theme');
let currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');

document.documentElement.setAttribute('data-theme', currentTheme);
updateThemeAssets(currentTheme);

function updateThemeAssets(theme) {
    const icon = document.getElementById("header-icon");
    const light_themeIcon = document.getElementById("light-themeIcon");
    const dark_themeIcon = document.getElementById("dark-themeIcon");
    const send_icon = document.getElementById("send-icon");

    if (theme === 'light') {
        light_themeIcon.src = "/static/icons/light.svg";
        dark_themeIcon.src = "/static/icons/dark-mode.svg";
        icon.src = "/static/icons/logo-bg-removed.png";
        send_icon.src = "/static/icons/send-dark.svg";
    } else {
        light_themeIcon.src = "/static/icons/light-light.svg";
        dark_themeIcon.src = "/static/icons/dark-dark.svg";
        icon.src = "/static/icons/logo-dark-removebg-preview-cp.png";
        send_icon.src = "/static/icons/send-light.svg";
    }
}

function toggleTheme() {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    updateThemeAssets(currentTheme);
}

function setFaviconForSystemTheme(e){
    const prefersDark = e.matches ?? window.matchMedia('(prefers-color-scheme: dark)').matches;
    const favicon = document.querySelector('link[rel~="icon"]');

    if(prefersDark){
        favicon.href = '/static/icons/favicon_light.ico';
    }else{
        favicon.href = '/static/icons/favicon_dark.ico';
    }
}
setFaviconForSystemTheme({ matches: window.matchMedia('(prefers-color-scheme: dark)').matches }) //call setFaviconForSystemTheme on page load
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', setFaviconForSystemTheme)


// ===============================
// 🚀 Streaming Toggle Management (NEW)
// ===============================
const streamToggle = document.getElementById('stream-toggle');
let isStreamingEnabled = true; // Default state

function toggleStreaming() {
    isStreamingEnabled = !isStreamingEnabled; // Invert the current state
    
    // Update the button's appearance based on the state
    if (isStreamingEnabled) {
        streamToggle.setAttribute('data-stream-enabled', 'true');
    } else {
        streamToggle.removeAttribute('data-stream-enabled');
    }
    
    // Save the user's preference to local storage
    localStorage.setItem('streamingEnabled', isStreamingEnabled);
}

function initializeStreamingState() {
    const savedState = localStorage.getItem('streamingEnabled');
    // If a state is saved, use it. Otherwise, default to true.
    isStreamingEnabled = savedState === null ? true : savedState === 'true';

    if (isStreamingEnabled) {
        streamToggle.setAttribute('data-stream-enabled', 'true');
    } else {
        streamToggle.removeAttribute('data-stream-enabled');
    }
}
// ===============================
// 🌐 Mode Management
// ===============================
let currentMode = "automatic"; // default

function initializeModeState() {
    const savedMode = localStorage.getItem("chatMode");
    const modeDropdown = document.getElementById("mode-dropdown");

    // Pick saved mode > dropdown default > fallback "automatic"
    currentMode = savedMode || modeDropdown?.value || "automatic";

    if (modeDropdown) {
        modeDropdown.value = currentMode; // restore selection
        modeDropdown.addEventListener("change", (e) => {
            currentMode = e.target.value;
            localStorage.setItem("chatMode", currentMode);
            console.log("Mode switched to:", currentMode);
        });
    }
}

function getCurrentMode() {
    return currentMode;
}




// ===============================
// ✨ DOM References & Globals
// ===============================
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const chatSuggestions = document.getElementById('chat-suggestions');
const suggestionButtonsContainers = chatSuggestions.querySelector('.suggestion-buttons');
let currentBotMessageDiv = null;
let controller = null;
let isUserScrolling = false; // Track if user is manually scrolling
let scrollTimeout = null;
let currentSessionId = null; // Store current session ID

// ===============================
// 🧠 Utility Functions
// ===============================
function setUserInput(text) {
    userInput.value = text;
    userInput.focus();
}

function formatMarkdown(text) {
    if (!text) return "";
    return marked.parse(text);
}

function isUserAtBottom(chatMessages, threshold = 50) {
    return chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < threshold;
}

// Enhanced scroll behavior detection
function handleUserScroll() {
    isUserScrolling = true;
    
    // Clear existing timeout
    if (scrollTimeout) {
        clearTimeout(scrollTimeout);
    }
    
    // Reset the scrolling flag after user stops scrolling
    scrollTimeout = setTimeout(() => {
        isUserScrolling = false;
    }, 150); // 150ms delay after user stops scrolling
}

// Add scroll event listener to detect manual scrolling
chatMessages.addEventListener('scroll', handleUserScroll, { passive: true });

// ===============================
// 📝 Auto-resize Input Textarea
// ===============================
userInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 128) + 'px';
});

// ===============================
// 💬 Chat Message Handling
// ===============================
function appendMessage(sender, messageContent) {
    console.log('User is ', sender);
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message-bubble');

    if (sender === 'user') {
        messageDiv.classList.add('user-message');
        messageDiv.textContent = messageContent;
    } else {
        messageDiv.classList.add('bot-message');
        const responseContentDiv = document.createElement('div');
        responseContentDiv.classList.add('bot-response-content');
        messageDiv.appendChild(responseContentDiv);
    }

    chatMessages.appendChild(messageDiv);
    
    // Only auto-scroll for new messages if user isn't manually scrolling
    if (!isUserScrolling) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    // // If it's a bot message, add feedback section
    // if (sender === 'bot') {
    //     // Assuming your backend returns message_id after saving message
    //     // For now, you can generate a temporary UUID until integration:
    //     // const tempMessageId = crypto.randomUUID();
    //     addFeedbackSection(messageDiv);
    // }

    
    return messageDiv;
}

// Smart scroll function that respects user intent
function smartScroll() {
    // Only auto-scroll if:
    // 1. User is not currently scrolling manually
    // 2. User is near the bottom of the chat
    if (!isUserScrolling && isUserAtBottom(chatMessages)) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// ===============================
// 📩 Send Message (with SSE streaming)
// ===============================
async function sendMessage() {
    chatSuggestions.style.display = 'none';

    const message = userInput.value.trim();
    if (message === '') {
        showCustomModal("Please enter a message before sending.");
        return;
    }

    appendMessage('user', message);
    userInput.value = '';
    userInput.style.height = 'auto';
    sendButton.disabled = true;

    const loadingIndicator = document.getElementById('loading-indicator');
    const loadingTextContainer = document.getElementById('loading-text-container');
    loadingIndicator.style.display = 'block';
    loadingTextContainer.textContent = "Processing your query...";

    currentBotMessageDiv = appendMessage('bot', '');
    const responseContentTarget = currentBotMessageDiv.querySelector('.bot-response-content');

    if (controller) controller.abort();
    controller = new AbortController();

    try {
        // Prepare headers with session ID for FastAPI
        const headers = {
            'Content-Type': 'application/json'
        };
        if (currentSessionId) {
            headers['X-Session-ID'] = currentSessionId;
        }
        const streamingEnabledAttr = streamToggle.hasAttribute('data-stream-enabled');
        const currentModeAttr = document.getElementById('mode-dropdown').value;

                // ... before: you already prepared headers and did fetch(...)
        const response = await fetch('/stream_chat', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ 
                message, 
                streaming_enabled: streamingEnabledAttr, 
                current_mode: currentModeAttr 
            }),
            signal: controller.signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            // parse errorText as you already do...
            throw new Error(errorText);
        }

        const contentType = response.headers.get('content-type') || '';

        // If backend returned SSE (streaming), handle as before
        if (contentType.includes('text/event-stream') || streamingEnabledAttr) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '', streamedContent = '';
            let sourcesAdded = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Split into complete events
                let events = buffer.split("\n\n");
                buffer = events.pop(); // keep incomplete part

                for (const eventString of events) {
                    const dataMatch = eventString.match(/data: (.*)/);
                    if (!dataMatch) continue;

                    let parsedData;
                    try {
                        parsedData = JSON.parse(dataMatch[1]);
                    } catch (e) {
                        console.warn("Invalid SSE JSON:", dataMatch[1]);
                        continue;
                    }

                    if (parsedData.pipeline_step) {
                        loadingTextContainer.textContent = parsedData.pipeline_step;
                        continue;
                    }

                    if (parsedData.status === 'DONE') {
                        sendButton.disabled = false;
                        loadingIndicator.style.display='none';
                        if (currentBotMessageDiv && !currentBotMessageDiv.querySelector('.feedback-container')) {
                            addFeedbackSection(currentBotMessageDiv);
                        }
                        smartScroll();
                        continue;
                    }

                    if (parsedData.error) {
                        showCustomModal(`Streaming error: ${parsedData.error}`);
                        currentBotMessageDiv.innerHTML = formatMarkdown(`⚠️ Error: ${parsedData.error}`);
                        return;
                    }

                    if (parsedData.chunk) {
                        loadingIndicator.style.display = 'none';
                        streamedContent += parsedData.chunk;
                        responseContentTarget.innerHTML = formatMarkdown(streamedContent);
                        smartScroll();
                    }

                    if (parsedData.sql_query) {
                        const sourcesContainer = document.createElement('div');
                        sourcesContainer.classList.add('source-container');
                        sourcesContainer.innerHTML = `<strong>Executed SQL Query:</strong><pre><div class="source-line">${parsedData.sql_query}</div></pre>`;
                        currentBotMessageDiv.appendChild(sourcesContainer);
                        smartScroll();
                    }

                    if (parsedData.sources && !sourcesAdded) {
                        const sourcesHtml = parsedData.sources.map(src => `<div class="source-line">${src}</div>`).join('');
                        const sourcesContainer = document.createElement('div');
                        sourcesContainer.classList.add('source-container');
                        sourcesContainer.innerHTML = `<strong>Sources:</strong>${sourcesHtml}`;
                        currentBotMessageDiv.appendChild(sourcesContainer);
                        sourcesAdded = true;
                        smartScroll();
                    }

                    if(parsedData.message_id){
                        try {
                            if(currentBotMessageDiv){
                                currentBotMessageDiv.dataset.messageId = parsedData.message_id;
                            }
                            if(!currentBotMessageDiv.querySelector('.feedback-container')){
                                addFeedbackSection(currentBotMessageDiv);
                            }
                        }
                        catch(e) {
                            console.warn("Failed to attach message_id in DOM: ", e)
                        }
                    }
                }
            }
        } else {
            // Non-streaming path: parse JSON and render the whole response at once
            const jsonData = await response.json();
            const fullText = jsonData.response || '';
            loadingIndicator.style.display = 'none';
            responseContentTarget.innerHTML = formatMarkdown(fullText);
            sendButton.disabled = false;

            // If backend returned sql_query or sources, render them similarly to streaming logic:
            if (jsonData.sql_query) {
                const sourcesContainer = document.createElement('div');
                sourcesContainer.classList.add('source-container');
                sourcesContainer.innerHTML = `<strong>Executed SQL Query:</strong><pre><div class="source-line">${jsonData.sql_query}</div></pre>`;
                currentBotMessageDiv.appendChild(sourcesContainer);
            }
            if (jsonData.sources && jsonData.sources.length) {
                const sourcesHtml = jsonData.sources.map(src => `<div class="source-line">${src}</div>`).join('');
                const sourcesContainer = document.createElement('div');
                sourcesContainer.classList.add('source-container');
                sourcesContainer.innerHTML = `<strong>Sources:</strong>${sourcesHtml}`;
                currentBotMessageDiv.appendChild(sourcesContainer);
            }
            if (jsonData.message_id){
                if(currentBotMessageDiv){
                    currentBotMessageDiv.dataset.messageId=jsonData.message_id;
                    if(!currentBotMessageDiv.querySelector('.feedback-container')){
                        addFeedbackSection(currentBotMessageDiv);
                    }
                }
            }

            smartScroll();
        }
    } catch (error) {
        if (error.name === 'AbortError') return;

        // Log error to FastAPI backend
        fetch('/frontend_log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: "fetch_stream_error",
                error_message: error.message,
                stack: error.stack,
                user_prompt: message,
                user_agent: navigator.userAgent
            })
        });

        showCustomModal(`Failed to get response: ${error.message}. Please check the server logs.`);
        if (currentBotMessageDiv) {
            currentBotMessageDiv.innerHTML = formatMarkdown("Sorry, something went wrong. Please try again.");
        }

    } finally {
        loadingIndicator.style.display = 'none';
        sendButton.disabled = false;
        smartScroll(); // Use smart scroll instead of forcing
    }
}

// ===============================
// 💡 Suggestions Handling
// ===============================
async function loadChatSuggestions() {
    try {
        const response = await fetch('/suggestions');
        if (!response.ok) throw new Error(`HTTP Error! Status ${response.status}`);

        const suggestions = await response.json();
        displayRandomSuggestions(suggestions, 3);

    } catch (error) {
        console.error("Failed to load chat suggestions:", error);
        if (chatSuggestions) chatSuggestions.style.display = 'none';
    }
}

function displayRandomSuggestions(suggestions, count) {
    if (!suggestionButtonsContainers || !suggestions || suggestions.length === 0) {
        chatSuggestions.style.display = 'none';
        return;
    }

    suggestionButtonsContainers.innerHTML = '';
    const shuffled = suggestions.sort(() => 0.5 - Math.random());
    const selected = shuffled.slice(0, Math.min(count, suggestions.length));

    selected.forEach(suggestionText => {
        const button = document.createElement('button');
        button.classList.add('suggestion-btn');
        button.textContent = suggestionText;
        button.onclick = () => setUserInput(suggestionText);
        suggestionButtonsContainers.appendChild(button);
    });
}

// ===============================
// 🔗 Session Management
// ===============================
async function startSession() {
    try {
        const response = await fetch('/start_session', { method: 'GET' });
        if (!response.ok) throw new Error(`HTTP Error! Status ${response.status}`);
        
        const data = await response.json();
        currentSessionId = data.session_id;
        console.log('Session started:', data);
        return data;
    } catch (error) {
        console.error('Failed to start session:', error);
        return null;
    }
}

async function endSession() {
    if (!currentSessionId) return;
    
    try {
        const headers = {
            'Content-Type': 'application/json',
            'X-Session-ID': currentSessionId
        };
        
        const response = await fetch('/end_session', {
            method: 'POST',
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Session ended:', data);
        }
    } catch (error) {
        console.error('Failed to end session:', error);
    }
}

// ===============================
// 🚀 Event Listeners
// ===============================
sendButton.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

window.onload = async () => {
    userInput.focus();
    loadChatSuggestions();

    // Init states
    initializeStreamingState();
    initializeModeState();
    
    // Start session on page load
    await startSession();
};

// Handle page unload - end session
window.addEventListener("beforeunload", () => {
    if (currentSessionId) {
        // Use sendBeacon for reliable cleanup on page unload
        const headers = {
            'Content-Type': 'application/json',
            'X-Session-ID': currentSessionId
        };
        
        // Note: sendBeacon doesn't support custom headers, so we'll use fetch with keepalive
        fetch('/end_session', {
            method: 'POST',
            headers: headers,
            keepalive: true
        }).catch(() => {
            // Ignore errors during unload
        });
    }
});

// ===============================
// 🛡️ Error Logging
// ===============================
window.onerror = function (message, source, lineno, colno, error) {
    console.error("Global JS Error:", { message, source, lineno, colno, error });

    fetch('/frontend_log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: "js_runtime_error",
            message,
            source,
            lineno,
            colno,
            error_stack: error?.stack,
            user_agent: navigator.userAgent
        })
    }).catch(() => {
        // Ignore logging errors to prevent infinite loops
    });
};

window.addEventListener('unhandledrejection', function (event) {
    console.error("Unhandled Promise Rejection:", event.reason);
    fetch('/frontend_log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            type: "unhandled_promise_rejection",
            reason: event.reason?.toString() || 'Unknown error',
            user_agent: navigator.userAgent
        })
    }).catch(() => {
        // Ignore logging errors to prevent infinite loops
    });
});

// ===============================
// 📱 Custom Modal Function (if not defined elsewhere)
// ===============================
function showCustomModal(message) {
    // Simple implementation - replace with your actual modal function
    alert(message);
}

// ===============================
// ❤️ Feedback System
// ===============================
function addFeedbackSection(messageDiv) {
    // Only for bot messages
    if (!messageDiv.classList.contains('bot-message')) return;
    if (messageDiv.querySelector('.feedback-container')) return;

    const feedbackHTML = `
        <div class="feedback-container">
            <button class="feedback-btn like-btn" onclick="handleFeedback(this, 'like')">👍</button>
            <button class="feedback-btn dislike-btn" onclick="handleFeedback(this, 'dislike')">👎</button>
            <div class="feedback-textbox hidden">
                <textarea placeholder="What went wrong?" rows="2"></textarea>
                <button class="submit-feedback-btn" onclick="submitFeedback(this)">Send</button>
            </div>
        </div>
    `;

    messageDiv.insertAdjacentHTML('beforeend', feedbackHTML);
}

function handleFeedback(btn, type) {
    const container = btn.closest('.feedback-container');
    const likeBtn = container.querySelector('.like-btn');
    const dislikeBtn = container.querySelector('.dislike-btn');
    const textbox = container.querySelector('.feedback-textbox');

    if (type === 'like') {
        likeBtn.classList.toggle('active');
        dislikeBtn.classList.remove('active');
        textbox.classList.add('hidden');

        if (likeBtn.classList.contains('active')) {
            sendFeedback(container, 'like', '');
        }
    } else {
        dislikeBtn.classList.toggle('active');
        likeBtn.classList.remove('active');
        textbox.classList.toggle('hidden', !dislikeBtn.classList.contains('active'));
    }
}

function submitFeedback(btn) {
    const textbox = btn.closest('.feedback-textbox');
    const container = textbox.closest('.feedback-container');
    const text = textbox.querySelector('textarea').value.trim();

    if (text) {
        sendFeedback(container, 'dislike', text);
        textbox.innerHTML = "<em>Thanks for your feedback!</em>";
    }
}

function sendFeedback(container, type, comment) {
    const messageElement = container.closest('.message-bubble');
    const message_id = messageElement?.dataset.messageId;
    const session_id = currentSessionId;

    if (!message_id || !session_id) {
        console.warn("Missing IDs for feedback submission");
        return;
    }

    // simple guard: mark as submitted on the dataset
    const key = `feedback_submitted_${type}`;
    if (messageElement.dataset[key]) {
        console.log("Feedback already submitted for this message and type.");
        return;
    }
    messageElement.dataset[key] = "1";

    fetch('/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message_id,
            session_id,
            feedback_type: type,
            comment
        })
    })
    .then(res => res.json())
    .then(data => console.log("✅ Feedback stored:", data))
    .catch(err => console.error("❌ Feedback error:", err));
}
