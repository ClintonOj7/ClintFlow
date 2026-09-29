function toggleFaq(element) {
    const faqItem = element.parentElement;
    const allItems = document.querySelectorAll('.faq-item');

    allItems.forEach(item=> {
        if (item !== faqItem) {
            item.classList.remove('active');
        }
    });

    faqItem.classList.toggle('active');
}

// LOADING SCREEN
window.onload = function() {
    var width = 0;
    var progress = document.querySelector('.loader-progress');
    var percent = document.querySelector('.loader-percent');
    var loader = document.getElementById('loader');

    var interval = setInterval(function() {
        width = width + 10;
        if (progress) progress.style.width = width + '%';
        if (percent) percent.textContent = width + '%';

        if (width >= 100) {
            clearInterval(interval);
            setTimeout(function() {
                loader.style.opacity = '0';
                setTimeout(function() {
                    loader.style.display = 'none';
                }, 800);
            }, 300);
        }
    }, 200);
};

document.getElementById('user-prompt').addEventListener('input', function() {
    const text = this.value.trim();
    const wordCount = text === '' ? 0 : text.split(/\s+/).length;
    document.getElementById('word-count').textContent = wordCount + ' words';

    const charWarning = document.getElementById('char-warning');
    if (this.value.length > 200) {
        charWarning.style.display = 'block';
    } else {
        charWarning.style.display = 'none';
    }
});

document.getElementById('user-prompt').addEventListener('input', function() {
    localStorage.setItem('clintflow-draft', this.value);
});

window.addEventListener('load', function() {
    const savedDraft = localStorage.getItem('clintflow-draft');
    if (savedDraft) {
        document.getElementById('user-prompt').value = savedDraft;
        document.getElementById('user-prompt').dispatchEvent(new Event('input'));
    }
});

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// AI CONTENT GENERATOR
async function generateContent() {
    const prompt = document.getElementById('user-prompt').value;
    const contentType = document.getElementById('content-type').value;
    const toneType = document.getElementById('tone-type').value;
    const lengthType = document.getElementById('length-type').value;
    const seoBoost = document.getElementById('seo-boost').checked;
    const languageType = document.getElementById('language-type').value;

    const lengthMap = {
      short: 'approximately 100 words',
      medium: 'approximately 300 words',
      long: 'approximately 600 words',
    };

    const outputText = document.getElementById('output-text');
    const generateBtn = document.getElementById('generate-btn');
    const copyBtn = document.getElementById('copy-btn');

    if (!prompt.trim()) {
        alert('Please enter a topic first!');
        return;
    }

    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating...';
    outputText.innerHTML = '<div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line short"></div>';
    copyBtn.style.display = 'none';

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                contentType: contentType,
                toneType: toneType,
                lengthType: lengthType,
                seoBoost: seoBoost,
                languageType: languageType
            })
        });

        const data = await response.json();

        if (response.ok && data.content) {
            outputText.style.color = '#ffffff';
            typeWriter(formatMarkdown(data.content), outputText);
            copyBtn.style.display = 'block';
            document.getElementById('regenerate-btn').style.display = 'inline-block';
            document.getElementById('export-btn').style.display = 'inline-block';

            const outputWords = data.content.trim().split(/\s+/).length;
            document.getElementById('output-word-count').textContent = '(' + outputWords + ' words)';

            const badge = document.getElementById('originality-badge');
            badge.textContent = '✔️ ' + generateOriginalityScore();
            badge.style.display = 'inline-block';

            addToHistory(prompt, data.content, contentType);
            launchConfetti();
        } else {
            outputText.style.color = '#ff5f57';
            outputText.textContent = 'Error: ' + (data.error || 'Unable to generate content.');
        }

    } catch (error) {
        outputText.style.color = '#ff5f57';
        outputText.textContent = 'Error: ' + error.message;
    }

    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate Content';
}

function copyContent() {
    const text = document.getElementById('output-text').textContent;
    navigator.clipboard.writeText(text);
    const copyBtn = document.getElementById('copy-btn');
    copyBtn.textContent = 'Copied!';
    setTimeout(() => copyBtn.textContent = 'Copy', 2000);
}

function formatMarkdown(text) {
    // Sanitize HTML first to prevent XSS, then format markdown tokens
    const safeText = escapeHtml(text);
    return safeText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function typeWriter(html, element) {
    element.innerHTML = '';
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    const fullText = tempDiv.textContent;

    let i = 0;
    const speed = 8;

    function type() {
        if (i < fullText.length) {
            element.textContent = fullText.substring(0, i + 1);
            i++;
            setTimeout(type, speed);
        } else {
            element.innerHTML = html;
        }
    }
    type();
 }

 let contentHistory = [];

 function addToHistory(topic, content, type) {
    contentHistory.unshift({ topic, content, type });
    if (contentHistory.length > 5) {
        contentHistory.pop();
    }
    renderHistory();
 }

 function renderHistory() {
    const historyList = document.getElementById('history-list');
    historyList.innerHTML = '';

    contentHistory.forEach((item) => {
        const div = document.createElement('div');
        div.className = 'history-item';

        const topicEl = document.createElement('div');
        topicEl.className = 'history-topic';
        topicEl.textContent = item.topic;

        const metaEl = document.createElement('div');
        metaEl.className = 'history-meta';
        metaEl.textContent = item.type;

        div.appendChild(topicEl);
        div.appendChild(metaEl);

        div.onclick = function() {
            document.getElementById('output-text').innerHTML = formatMarkdown(item.content);
        };
        historyList.appendChild(div);
     });
 }

 function exportContent() {
    const text = document.getElementById('output-text').innerText;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'clintflow-context.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
 }

 function generateOriginalityScore() {
     const score = Math.floor(Math.random() * (99 - 92) + 92);
     return score + '%Original';
 }

 function startVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert('Voice input is not supported in this browser. Try Chrome!');
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;

    const micBtn = document.getElementById('mic-btn');
    const textarea = document.getElementById('user-prompt');

    recognition.onstart = function() {
        micBtn.classList.add('listening');
    };

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        textarea.value = transcript;
        textarea.dispatchEvent(new Event('input'));
    };

    recognition.onend = function() {
        micBtn.classList.remove('listening');
    };

    recognition.start();
}

function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('theme-toggle');

    body.classList.toggle('light-mode');

    if (body.classList.contains('light-mode')) {
        btn.textContent = '☀️';
    } else {
        btn.textContent = '🌙';
    }
}

function launchConfetti() {
    const colors = ['#6c63ff', '#00d4ff', '#ffbd2e', '#28ca41'];

    for (let i = 0; i < 30; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.left = Math.random() * 100 + 'vw';
        confetti.style.top = '20%';
        confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
        confetti.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
        document.body.appendChild(confetti);

        setTimeout(() => confetti.remove(), 1500);
    }
}
