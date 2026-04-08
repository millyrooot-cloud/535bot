/**
 * Kelley Compass AI - State-Based Single Screen App
 * Three states: Landing → Confirmation → Chat + Recommendations
 */

// State Management
let currentState = 'landing'; // landing | confirm | chat
let parsedProfile = null;
let conversationHistory = [];
let recommendations = [];
let isLoading = false;

// DOM Elements
const stateLanding = document.getElementById('state-landing');
const stateConfirm = document.getElementById('state-confirm');
const stateChat = document.getElementById('state-chat');

const fileDropZone = document.getElementById('fileDropZone');
const transcriptFile = document.getElementById('transcriptFile');
const chatForm = document.getElementById('chatForm');
const chatInputMain = document.getElementById('chatInputMain');
const chatMessages = document.getElementById('chatMessages');
const fileStatus = document.getElementById('fileStatus');
const fileStatusContent = document.getElementById('fileStatusContent');

// Confirm state elements
const confirmEdit = document.getElementById('confirmEdit');
const confirmProceed = document.getElementById('confirmProceed');

// Chat state elements
const chatFormMain = document.getElementById('chatFormMain');
const recommendationsList = document.getElementById('recommendationsList');

// Demo selector
const demoSelect = document.getElementById('demoSelect');

// ============================================================================
// DEMO TRANSCRIPT LOADING
// ============================================================================

async function loadDemoTranscripts() {
    try {
        const response = await fetch('/api/demo-transcripts');
        const data = await response.json();

        if (data.transcripts && demoSelect) {
            data.transcripts.forEach(transcript => {
                const option = document.createElement('option');
                option.value = transcript.id;
                option.textContent = transcript.name;
                demoSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load demo transcripts:', error);
    }
}

async function loadDemo(demoId) {
    if (!demoId) return;

    try {
        showFileStatus('success', '📖 Loading demo transcript...');
        const response = await fetch(`/api/load-demo/${demoId}`);
        const data = await response.json();

        if (data.error) {
            showFileStatus('error', `Error: ${data.error}`);
            return;
        }

        // Parse and process the transcript
        const file = new File(
            [data.transcript_text],
            data.filename,
            { type: 'text/plain' }
        );
        await handleFileUpload(file);

        // Reset dropdown
        demoSelect.value = '';
    } catch (error) {
        console.error('Failed to load demo:', error);
        showFileStatus('error', 'Failed to load demo transcript');
    }
}

// Handle demo selection
if (demoSelect) {
    demoSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            loadDemo(e.target.value);
        }
    });
}

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

function setState(newState) {
    currentState = newState;

    // Hide all states
    stateLanding.classList.remove('state-active');
    stateConfirm.classList.remove('state-active');
    stateChat.classList.remove('state-active');

    // Show current state
    switch (newState) {
        case 'landing':
            stateLanding.classList.add('state-active');
            break;
        case 'confirm':
            stateConfirm.classList.add('state-active');
            break;
        case 'chat':
            stateChat.classList.add('state-active');
            chatInputMain.focus();
            break;
    }
}

// ============================================================================
// FILE UPLOAD HANDLING
// ============================================================================

if (fileDropZone && transcriptFile) {
    fileDropZone.addEventListener('click', () => transcriptFile.click());

    fileDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropZone.classList.add('dragover');
    });

    fileDropZone.addEventListener('dragleave', () => {
        fileDropZone.classList.remove('dragover');
    });

    fileDropZone.addEventListener('drop', async (e) => {
        e.preventDefault();
        fileDropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) await handleFileUpload(files[0]);
    });

    transcriptFile.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (files.length > 0) await handleFileUpload(files[0]);
    });
}

async function handleFileUpload(file) {
    fileDropZone.classList.add('loading');

    // Show initial loading message with filename
    showFileStatus('success', `📖 Reading ${file.name}...`);

    try {
        // Read the file
        const text = await readFile(file);

        if (!text.trim()) {
            throw new Error('File is empty. Please check your transcript file.');
        }

        // Show parsing message
        showFileStatus('success', `✓ File loaded (${text.length} characters)\n⏳ Parsing transcript...`);

        // Parse the transcript
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile: {},
                transcript_text: text,
                message: 'Please parse this transcript.'
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Server error while parsing transcript');
        }

        const data = await response.json();

        // Validate parse results
        if (!data.parsed_profile) {
            throw new Error('Could not parse transcript. Please check the format.');
        }

        if (!data.parsed_profile.student_name || data.parsed_profile.student_name === 'Student') {
            showFileStatus('warning', `⚠️ Could not extract student name. Proceeding anyway...`);
        }

        if (!data.parsed_profile.courses || data.parsed_profile.courses.length === 0) {
            throw new Error('No courses found in transcript. Please check the format and try again.');
        }

        // Store parsed data
        parsedProfile = data.parsed_profile || {};
        recommendations = data.recommendations || [];

        // Show success confirmation
        showFileStatus('success', `✅ Successfully parsed ${data.parsed_profile.courses.length} courses\n👤 Student: ${data.parsed_profile.student_name}\n📊 I-Core: ${Math.round(data.parsed_profile.icore_percent || 0)}%`);

        // Wait a moment to let user see the success message
        await new Promise(resolve => setTimeout(resolve, 1500));

        // Move to confirmation state
        showConfirmation(parsedProfile);
        setState('confirm');

    } catch (error) {
        console.error('File error:', error);
        showFileStatus('error', `Error: ${error.message}\n\nTry uploading again or paste your transcript below.`);
    } finally {
        fileDropZone.classList.remove('loading');
        transcriptFile.value = '';
    }
}

function readFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const result = e.target?.result;
            if (typeof result === 'string') {
                resolve(result);
            } else {
                // PDF text extraction (basic)
                const view = new Uint8Array(result);
                let text = '';
                for (let i = 0; i < view.length; i++) {
                    const code = view[i];
                    if ((code >= 32 && code <= 126) || code === 10 || code === 13) {
                        text += String.fromCharCode(code);
                    }
                }
                resolve(text);
            }
        };
        reader.onerror = () => reject(new Error('Failed to read file'));

        if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
            reader.readAsArrayBuffer(file);
        } else {
            reader.readAsText(file);
        }
    });
}

function showFileStatus(type, message) {
    fileStatus.className = `file-status ${type}`;
    fileStatusContent.innerHTML = message;
    fileStatus.style.display = 'block';

    // Don't auto-hide loading/processing messages
    if (type === 'success' && !message.includes('...')) {
        // Only auto-hide if it's a final success (doesn't have "..." in it)
        setTimeout(() => {
            if (fileStatus.style.display === 'block') {
                // fileStatus.style.display = 'none';
            }
        }, 5000);
    }
}

// ============================================================================
// TRANSCRIPT PARSING
// ============================================================================

async function parseTranscript(transcriptText, metadata = {}) {
    isLoading = true;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile: {},
                transcript_text: transcriptText,
                message: 'Please parse this transcript.' // Triggers parse mode
            })
        });

        if (!response.ok) throw new Error('Server error');
        const data = await response.json();

        // Store parsed profile
        parsedProfile = data.parsed_profile || {};
        recommendations = data.recommendations || [];

        // Move to confirmation state
        showConfirmation(parsedProfile);
        setState('confirm');

    } catch (error) {
        console.error('Parse error:', error);
        showFileStatus('error', `⚠️ Parse error: ${error.message}`);
    } finally {
        isLoading = false;
    }
}

// ============================================================================
// STATE 2: CONFIRMATION
// ============================================================================

function showConfirmation(profile) {
    // Student name and basic info
    document.getElementById('confirmName').textContent = profile.student_name || 'Student';

    const metaText = [];
    if (profile.matriculation_year) metaText.push(`Class of ${profile.matriculation_year}`);
    // Only show current_year if it's not "Unknown"
    if (profile.current_year && profile.current_year !== 'Unknown') {
        metaText.push(profile.current_year);
    }
    if (profile.declared_majors && profile.declared_majors.length > 0) {
        metaText.push(profile.declared_majors.join(', '));
    }
    document.getElementById('confirmMeta').textContent = metaText.join(' • ');

    // Stats boxes
    document.getElementById('confirmGPA').textContent = profile.gpa ? profile.gpa.toFixed(2) : '—';
    document.getElementById('confirmCredits').textContent = profile.total_credits ? profile.total_credits.toFixed(1) : '—';
    document.getElementById('confirmICoreValue').textContent = `${Math.round(profile.icore_percent || 0)}%`;

    // Courses list - display as chronological list
    const coursesList = document.getElementById('confirmCoursesList');
    if (profile.courses && profile.courses.length > 0) {
        // Organize by semester/term
        const coursesByTerm = {};
        profile.courses.forEach(c => {
            const term = c.term || 'Undated';
            if (!coursesByTerm[term]) {
                coursesByTerm[term] = [];
            }
            coursesByTerm[term].push(c);
        });

        // Display in chronological order
        let html = '';
        Object.keys(coursesByTerm).forEach(term => {
            if (term !== 'Undated') {
                html += `<div class="courses-term-header">${term}</div>`;
            }
            coursesByTerm[term].forEach(c => {
                html += `
                    <div class="course-list-item">
                        <span class="course-list-code">${c.code}</span>
                        <span class="course-list-title">${c.title || 'Course'}</span>
                        <span class="course-list-grade">${c.grade}</span>
                    </div>
                `;
            });
        });

        coursesList.innerHTML = html;
    } else {
        coursesList.innerHTML = '<div style="color: var(--text-secondary); font-style: italic;">No courses found</div>';
    }

    // Show warnings if any
    const warningsDiv = document.getElementById('confirmWarnings');
    if (profile.notes && profile.notes.length > 0) {
        document.getElementById('warningsContent').innerHTML = profile.notes.map(n => `<p>⚠️ ${escapeHtml(n)}</p>`).join('');
        warningsDiv.style.display = 'block';
    }
}

confirmEdit.addEventListener('click', () => {
    // Show edit mode
    const editMode = document.getElementById('editMode');
    editMode.style.display = 'block';

    // Pre-fill with current data
    document.getElementById('editStudentName').value = parsedProfile.student_name || '';
    document.getElementById('editDeclaredMajors').value = (parsedProfile.declared_majors || []).join(', ');
    document.getElementById('editCareerGoal').value = parsedProfile.career_interests || '';

    // Scroll to edit section
    editMode.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

// Cancel edit mode
document.getElementById('editCancel').addEventListener('click', () => {
    document.getElementById('editMode').style.display = 'none';
});

// Save edits (sanitized)
document.getElementById('editSave').addEventListener('click', () => {
    // Sanitize inputs - remove HTML tags and trim
    const sanitize = (str) => {
        return str
            .toString()
            .trim()
            .replace(/[<>]/g, '')  // Remove angle brackets
            .replace(/[&]/g, '&amp;')  // Escape ampersands
            .substring(0, 200);  // Limit length
    };

    const newName = sanitize(document.getElementById('editStudentName').value);
    const newMajors = sanitize(document.getElementById('editDeclaredMajors').value)
        .split(',')
        .map(m => m.trim())
        .filter(m => m.length > 0);
    const newCareerGoal = sanitize(document.getElementById('editCareerGoal').value);

    // Update parsed profile (in memory only, no file changes)
    parsedProfile.student_name = newName || 'Student';
    parsedProfile.declared_majors = newMajors;
    parsedProfile.career_interests = newCareerGoal;

    // Refresh display
    document.getElementById('confirmName').textContent = parsedProfile.student_name;
    const metaText = [];
    if (parsedProfile.matriculation_year) metaText.push(`Class of ${parsedProfile.matriculation_year}`);
    if (parsedProfile.declared_majors && parsedProfile.declared_majors.length > 0) {
        metaText.push(parsedProfile.declared_majors.join(', '));
    }
    document.getElementById('confirmMeta').textContent = metaText.join(' • ');

    // Hide edit mode
    document.getElementById('editMode').style.display = 'none';
    showFileStatus('success', '✅ Changes saved (in session)');
});

confirmProceed.addEventListener('click', async () => {
    if (!parsedProfile) return;

    // Get major and interests from confirmation form
    const majorInput = document.getElementById('confirmMajorInput').value.trim();
    const interestsInput = document.getElementById('confirmInterestsInput').value.trim();

    // Parse majors (comma-separated)
    const declaredMajors = majorInput
        ? majorInput.split(',').map(m => m.trim()).filter(m => m.length > 0)
        : [];

    // Update parsed profile with user-provided data
    parsedProfile.declared_majors = declaredMajors;
    parsedProfile.career_interests = interestsInput || 'Not specified';

    // Regenerate recommendations with actual profile data
    isLoading = true;
    addSystemMessage('Generating personalized recommendations based on your major...');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile: {
                    student_name: parsedProfile.student_name,
                    matriculation_year: parsedProfile.matriculation_year,
                    gpa: parsedProfile.gpa,
                    total_credits: parsedProfile.total_credits,
                    current_year_in_school: '2', // Estimate from graduation timeline
                    declared_majors: declaredMajors,
                    career_interests: interestsInput,
                    semester_planning_for: 'Next Semester',
                    credit_hours_preference: 15
                },
                transcript_text: '', // Already parsed
                message: 'Generate course recommendations based on my major and transcript',
                conversation_history: []
            })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.recommendations) {
                recommendations = data.recommendations;
            }
        }
    } catch (error) {
        console.error('Error regenerating recommendations:', error);
    }

    isLoading = false;

    // Show recommendations and move to chat state
    showRecommendations(parsedProfile, recommendations);
    showProfileHeader(parsedProfile);
    setState('chat');

    // Add initial message about recommendations
    const majorText = declaredMajors.length > 0
        ? ` ${declaredMajors.join(', ')} major`
        : '';
    addSystemMessage(`Based on your${majorText} and transcript, I've prepared ${recommendations.length} course recommendations for you. Feel free to ask follow-up questions!`);
});

// Exit button - return to landing state
document.getElementById('exitBtn').addEventListener('click', () => {
    setState('landing');
    // Reset data for new upload
    parsedProfile = null;
    recommendations = [];
    conversationHistory = [];
    chatMessages.innerHTML = '';
    chatInputMain.value = '';
});

// ============================================================================
// STATE 3: RECOMMENDATIONS + CHAT
// ============================================================================

function showProfileHeader(profile) {
    document.getElementById('profileName').textContent = profile.student_name || 'Student';

    const majorText = profile.declared_majors && profile.declared_majors.length > 0
        ? profile.declared_majors.join(', ')
        : 'Not declared';
    document.getElementById('profileMajor').textContent = `📚 ${majorText}`;

    const icorePercent = Math.round(profile.icore_percent || 0);
    document.getElementById('profileICoreStatus').textContent = `📊 I-Core: ${icorePercent}%`;
}

function showRecommendations(profile, recs) {
    recommendationsList.innerHTML = recs
        .map((rec, idx) => `
            <div class="recommendation-card">
                <div class="rec-header">
                    <div>
                        <div class="rec-code">${rec.code}</div>
                        <div class="rec-title">${rec.title}</div>
                    </div>
                    <div class="rec-credits">${rec.credits} cr</div>
                </div>
                <div class="rec-reason">${rec.reason}</div>
                ${rec.prerequisites_met ? '<div class="rec-prereq">✓ Prerequisites met</div>' : ''}
                ${rec.warning ? `<div class="rec-warning">⚠ ${rec.warning}</div>` : ''}
            </div>
        `)
        .join('');
}

// ============================================================================
// UTILITY FUNCTIONS - INPUT SANITIZATION
// ============================================================================

function sanitizeInput(str) {
    /**
     * Sanitize user input to prevent XSS attacks.
     * - Remove dangerous characters
     * - Limit length
     * - Escape special characters
     */
    return str
        .substring(0, 1000)  // Max 1000 characters
        .replace(/[<>{}]/g, '')  // Remove brackets
        .replace(/javascript:/gi, '')  // Remove javascript: protocol
        .replace(/on\w+\s*=/gi, '')  // Remove event handlers (onclick=, etc)
        .trim();
}

// ============================================================================
// CHAT HANDLING
// ============================================================================

chatFormMain.addEventListener('submit', handleChatSubmit);
chatForm.addEventListener('submit', handleLandingInput);

async function handleLandingInput(e) {
    e.preventDefault();
    const message = document.getElementById('chatInput').value.trim();
    if (!message) return;

    document.getElementById('chatInput').value = '';

    // Treat as transcript input
    await parseTranscript(message);
}

async function handleChatSubmit(e) {
    e.preventDefault();

    let message = chatInputMain.value.trim();
    if (!message || isLoading || !parsedProfile) return;

    // Sanitize input to prevent XSS
    message = sanitizeInput(message);

    chatInputMain.value = '';
    chatInputMain.style.height = 'auto';

    // Add user message
    addUserMessage(message);
    conversationHistory.push({ role: 'user', content: message });

    // Show typing indicator
    isLoading = true;
    chatInputMain.disabled = true;
    const loadingMsg = addTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile: parsedProfile,
                transcript_text: '',
                message: message,
                conversation_history: conversationHistory
            })
        });

        if (!response.ok) throw new Error('Server error');
        const data = await response.json();

        if (loadingMsg) loadingMsg.remove();

        addAssistantMessage(data.reply, data.model);
        conversationHistory.push({ role: 'assistant', content: data.reply });

    } catch (error) {
        console.error('Chat error:', error);
        if (loadingMsg) loadingMsg.remove();
        addErrorMessage(`Error: ${error.message}`);
    } finally {
        isLoading = false;
        chatInputMain.disabled = false;
        chatInputMain.focus();
        scrollChatToBottom();
    }
}

// ============================================================================
// MESSAGE DISPLAY
// ============================================================================

function addUserMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'message message-user';
    msg.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(msg);
    scrollChatToBottom();
}

function addAssistantMessage(text, model = null) {
    const msg = document.createElement('div');
    msg.className = 'message message-assistant';

    const formatted = text
        .split('\n')
        .map(line => escapeHtml(line))
        .map(line => line.replace(/\b((?:BUS|ECON|ENG|MATH|STAT)-[A-Z]?\s*\d{3})\b/g, '<strong>$1</strong>'))
        .join('<br>');

    let modelLabel = '';
    if (model && model !== 'none' && model !== 'unknown') {
        modelLabel = `<div style="font-size: 0.75rem; color: #6b7280; margin-top: 0.5rem; font-style: italic;">Powered by ${escapeHtml(model)}</div>`;
    }

    msg.innerHTML = `<div class="message-content">${formatted}${modelLabel}</div>`;
    chatMessages.appendChild(msg);
    scrollChatToBottom();
}

function addSystemMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'message message-system';
    msg.innerHTML = `<div class="message-content"><p>${escapeHtml(text)}</p></div>`;
    chatMessages.appendChild(msg);
    scrollChatToBottom();
}

function addTypingIndicator() {
    const msg = document.createElement('div');
    msg.className = 'message message-assistant';
    msg.innerHTML = `<div class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    </div>`;
    chatMessages.appendChild(msg);
    scrollChatToBottom();
    return msg;
}

function addErrorMessage(text) {
    const msg = document.createElement('div');
    msg.className = 'message message-system';
    msg.innerHTML = `<div class="message-content" style="color: #dc2626; border-left-color: #dc2626; background: #fee2e2;">
        <strong>⚠️ Error:</strong> ${escapeHtml(text)}
    </div>`;
    chatMessages.appendChild(msg);
    scrollChatToBottom();
}

function scrollChatToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

window.addEventListener('load', () => {
    setState('landing');
    loadDemoTranscripts();
});

// Auto-resize chat input
chatInputMain.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

// Handle Enter key to submit (Shift+Enter for new line)
chatInputMain.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatFormMain.dispatchEvent(new Event('submit'));
    }
});

document.getElementById('chatInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});
