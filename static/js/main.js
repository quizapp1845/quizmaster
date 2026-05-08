// Show flash messages with animation
function showMessage(message, type) {
    const toast = document.createElement('div');
    toast.className = `fixed top-20 right-4 z-50 p-4 rounded-lg shadow-lg fade-in-up ${type === 'success' ? 'bg-green-500' : type === 'danger' ? 'bg-red-500' : 'bg-blue-500'} text-white`;
    toast.innerHTML = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Quiz Management
let quizState = {
    currentQuestion: null,
    currentIndex: 0,
    totalQuestions: 0,
    selectedOption: null,
    timer: null,
    timeLeft: 30,
    topic: '',
    startTime: null
};

async function startQuiz(topic, numQuestions = 5) {
    try {
        const response = await fetch('/api/quiz/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, num_questions: numQuestions })
        });
        
        if (!response.ok) throw new Error('Failed to start quiz');
        
        const data = await response.json();
        quizState.currentQuestion = data;
        quizState.currentIndex = data.current;
        quizState.totalQuestions = data.total;
        quizState.topic = data.topic;
        quizState.selectedOption = null;
        quizState.startTime = Date.now();
        
        displayQuestion(data);
        startTimer(30);
        
        document.getElementById('quiz-setup').style.display = 'none';
        document.getElementById('quiz-area').style.display = 'block';
    } catch (error) {
        console.error('Error starting quiz:', error);
        showMessage('Failed to start quiz. Please try again.', 'danger');
    }
}

function displayQuestion(question) {
    document.getElementById('question-text').textContent = question.question_text;
    document.getElementById('current-q').textContent = question.current;
    document.getElementById('total-q').textContent = question.total;
    document.getElementById('topic-badge').textContent = question.topic;
    
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = '';
    
    const options = ['A', 'B', 'C', 'D'];
    question.options.forEach((opt, idx) => {
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.innerHTML = `<span class="font-bold mr-3">${options[idx]}.</span> ${opt}`;
        btn.onclick = () => selectOption(idx + 1, btn);
        optionsContainer.appendChild(btn);
    });
    
    updateProgress();
}

function selectOption(option, btnElement) {
    if (quizState.selectedOption !== null) return;
    
    quizState.selectedOption = option;
    document.querySelectorAll('.option-btn').forEach(btn => btn.classList.remove('selected'));
    btnElement.classList.add('selected');
    
    // Auto-submit after 1 second
    setTimeout(() => submitAnswer(), 500);
}

async function submitAnswer() {
    if (!quizState.selectedOption && quizState.timeLeft > 0) {
        showMessage('Please select an answer!', 'warning');
        return;
    }
    
    clearInterval(quizState.timer);
    const timeTaken = 30 - quizState.timeLeft;
    
    try {
        const response = await fetch('/api/quiz/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                selected_option: quizState.selectedOption || 0,
                time_taken: timeTaken 
            })
        });
        
        const data = await response.json();
        
        if (data.completed) {
            completeQuiz(data.score, data.total, data.percentage);
        } else {
            quizState.currentQuestion = data;
            quizState.currentIndex = data.current;
            quizState.selectedOption = null;
            displayQuestion(data);
            startTimer(30);
        }
    } catch (error) {
        console.error('Error submitting answer:', error);
        showMessage('Error submitting answer', 'danger');
    }
}

function startTimer(seconds) {
    if (quizState.timer) clearInterval(quizState.timer);
    
    quizState.timeLeft = seconds;
    updateTimerDisplay();
    
    quizState.timer = setInterval(() => {
        quizState.timeLeft--;
        updateTimerDisplay();
        
        if (quizState.timeLeft <= 0) {
            clearInterval(quizState.timer);
            showMessage('Time\'s up! Moving to next question...', 'warning');
            submitAnswer();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const timerElement = document.getElementById('timer');
    if (timerElement) {
        timerElement.textContent = quizState.timeLeft;
        const percentage = (quizState.timeLeft / 30) * 100;
        document.getElementById('timer-circle').style.background = `conic-gradient(#667eea ${360 - (percentage * 3.6)}deg, #e5e7eb 0deg)`;
    }
}

function updateProgress() {
    const percent = (quizState.currentIndex / quizState.totalQuestions) * 100;
    document.getElementById('progress-fill').style.width = `${percent}%`;
}

function completeQuiz(score, total, percentage) {
    document.getElementById('quiz-area').style.display = 'none';
    const resultsDiv = document.getElementById('quiz-results');
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = `
        <div class="text-center glass-card p-8 fade-in-up">
            <h2 class="text-3xl font-bold mb-4">Quiz Complete! 🎉</h2>
            <div class="stat-number text-6xl mb-4">${score}/${total}</div>
            <div class="text-xl mb-2">Your Score: ${percentage}%</div>
            <div class="text-gray-600 mb-6">Topic: ${quizState.topic}</div>
            <button onclick="location.reload()" class="btn-primary">Take Another Quiz</button>
            <button onclick="location.href='/dashboard'" class="btn-outline-glass ml-3">Go to Dashboard</button>
        </div>
    `;
}

// Dashboard Charts (using Chart.js if available)
function initDashboardCharts() {
    const ctx = document.getElementById('performance-chart');
    if (!ctx) return;
    
    // Simple bar chart without external library
    const topics = document.querySelectorAll('.topic-performance');
    const labels = [];
    const data = [];
    
    topics.forEach(topic => {
        labels.push(topic.dataset.topic);
        data.push(parseFloat(topic.dataset.score));
    });
    
    // Create simple bar chart using canvas
    if (typeof Chart !== 'undefined') {
        new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ label: 'Average Score (%)', data, backgroundColor: '#667eea' }] },
            options: { responsive: true, scales: { y: { beginAtZero: true, max: 100 } } }
        });
    }
}

// Filter history
function filterHistory() {
    const topic = document.getElementById('topic-filter').value;
    if (topic) {
        window.location.href = `/history?topic=${encodeURIComponent(topic)}`;
    } else {
        window.location.href = '/history';
    }
}

// Search functionality
function searchHistory() {
    const searchTerm = document.getElementById('search-input').value.toLowerCase();
    const rows = document.querySelectorAll('#history-table tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

// Initialize page-specific features
document.addEventListener('DOMContentLoaded', () => {
    // Topic selection on quiz page
    const topicCards = document.querySelectorAll('.topic-card');
    if (topicCards.length) {
        topicCards.forEach(card => {
            card.addEventListener('click', () => {
                const topic = card.dataset.topic;
                const numQuestions = document.getElementById('num-questions')?.value || 5;
                startQuiz(topic, parseInt(numQuestions));
            });
        });
    }
    
    // Initialize dashboard charts
    initDashboardCharts();
    
    // Add animation classes
    document.querySelectorAll('.glass-card').forEach((card, idx) => {
        card.style.animationDelay = `${idx * 0.1}s`;
        card.classList.add('fade-in-up');
    });
});

// Smooth scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
});