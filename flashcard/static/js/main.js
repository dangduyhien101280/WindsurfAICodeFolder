// Global variables
let cards = [];
let currentCardIndex = 0;
let currentCard = null;
let autoSpeak = false;
let isInitialLoad = true; // Add flag for initial load
let speechRate = 1.0; // Default speech rate

// POS color mapping
const POS_COLORS = {
    'noun': '#03A9F4',      // Vibrant Blue
    'verb': '#8BC34A',      // Vibrant Green
    'adjective': '#FFC107', // Vibrant Orange
    'adverb': '#FF9800',    // Vibrant Coral
    'preposition': '#9C27B0', // Vibrant Purple
    'pronoun': '#00BCD4',   // Vibrant Teal
    'conjunction': '#2196F3', // Vibrant Cyan
    'interjection': '#FF69B4', // Vibrant Pink
    'article': '#4CAF50', // Vibrant Lime
    'auxiliary verb': '#3F51B5', // Vibrant Indigo
    'modal verb': '#9E9E9E', // Vibrant Gray
};

// Box system functionality
function updateBoxStats() {
    fetch('/api/cards/stats')
        .then(response => response.json())
        .then(stats => {
            // Update box counts
            for (let i = 0; i < 6; i++) {
                const boxStats = stats[`box_${i}`];
                if (boxStats) {
                    const boxElement = document.querySelector(`.box[data-box="${i}"]`);
                    if (boxElement) {
                        boxElement.querySelector('.box-count').textContent = boxStats.count;
                    }
                }
            }

            // Update total progress
            document.getElementById('total').textContent = stats.total;
            const learnedCount = stats['box_5'] ? stats['box_5'].count : 0;
            document.getElementById('learned').textContent = learnedCount;
        })
        .catch(error => {
            console.error('Error fetching box stats:', error);
            showToast('Error loading box statistics');
        });
}

// Update the current box indicator
function updateBoxIndicator(boxNumber) {
    // Remove active class from all boxes
    document.querySelectorAll('.box').forEach(box => {
        box.classList.remove('active');
    });

    // Add active class to current box
    const currentBox = document.querySelector(`.box[data-box="${boxNumber}"]`);
    if (currentBox) {
        currentBox.classList.add('active');
    }
    
    // Update progress arrow position
    const progressBar = document.querySelector('.progress-bar');
    const arrow = document.querySelector('.progress-arrow');
    if (progressBar && arrow) {
        const boxWidth = progressBar.offsetWidth / 6;
        const newPosition = (boxWidth * boxNumber) + (boxWidth / 2);
        arrow.style.left = `${newPosition}px`;
    }
}

// Card management functions
function loadCards() {
    showLoading(true);
    fetch('/api/cards')
        .then(response => response.json())
        .then(data => {
            cards = data;
            updateCardCount();
            if (cards.length > 0) {
                isInitialLoad = true; // Set flag before showing first card
                showCard(0);
                isInitialLoad = false; // Reset flag after first card is shown
            }
            updateBoxStats();
        })
        .catch(error => {
            console.error('Error loading cards:', error);
            showToast('Error loading flashcards');
        })
        .finally(() => {
            showLoading(false);
        });
}

function showCard(index) {
    // Validate index and cards array
    if (index < 0 || index >= cards.length) {
        console.error('Invalid card index:', index);
        showToast('No more cards to show');
        return;
    }

    // Update current card and index
    currentCardIndex = index;
    currentCard = cards[currentCardIndex];

    // Get DOM elements with error checking
    const cardElement = document.getElementById('flashcard');
    const wordElement = document.getElementById('word');
    const meaningElement = document.getElementById('meaning');
    const exampleElement = document.getElementById('example');
    const ipaElement = document.getElementById('ipa');
    const posElement = document.getElementById('pos');  // New POS element

    // Validate DOM elements
    const elementsToCheck = [
        { element: cardElement, name: 'flashcard' },
        { element: wordElement, name: 'word' },
        { element: meaningElement, name: 'meaning' },
        { element: exampleElement, name: 'example' },
        { element: ipaElement, name: 'ipa' },
        { element: posElement, name: 'pos' }
    ];

    // Check if any required elements are missing
    const missingElements = elementsToCheck.filter(item => !item.element);
    if (missingElements.length > 0) {
        console.error('Missing DOM elements:', 
            missingElements.map(item => item.name).join(', '));
        showToast('Error displaying card. Check console.');
        return;
    }

    // Reset card state
    if (cardElement) {
        cardElement.classList.remove('flipped');
    }
    
    // Update card content
    wordElement.textContent = currentCard.word || 'No word';
    meaningElement.textContent = 'Tap to reveal meaning';
    exampleElement.textContent = '';
    ipaElement.textContent = currentCard.ipa || '';
    
    // Set POS with color
    if (currentCard.pos) {
        posElement.textContent = currentCard.pos.toUpperCase();
        posElement.style.backgroundColor = POS_COLORS[currentCard.pos.toLowerCase()] || '#7f8c8d'; // Default gray if not found
        posElement.style.display = 'inline-block';
    } else {
        posElement.textContent = 'N/A';
        posElement.style.backgroundColor = '#7f8c8d';
        posElement.style.display = 'inline-block';
    }

    // Update box number display
    updateBoxIndicator(currentCard.box_number);

    // Update card count
    updateCardCount();
    
    // Update next review date
    const nextReview = currentCard.next_review ? new Date(currentCard.next_review) : null;
    document.getElementById('studyDate').textContent = nextReview ? 
        `Next Review: ${nextReview.toLocaleDateString()}` : 
        'Next Review: Not scheduled';
        
    // Update progress
    document.getElementById('currentCard').textContent = index + 1;
    
    // Only auto-speak if card is loaded, not initial load, and auto-speak is enabled
    if (!isInitialLoad && autoSpeak && currentCard.word && !document.getElementById('flashcard').classList.contains('flipped')) {
        setTimeout(() => {
            speakWord();
        }, 100);
    }
}

function updateCardCount() {
    document.getElementById('totalCards').textContent = cards.length;
}

// Navigation functions
function showNextCard() {
    if (currentCardIndex < cards.length - 1) {
        showCard(currentCardIndex + 1);
    } else if (cards.length > 0) {
        showCard(0);
    }
}

function showPreviousCard() {
    if (currentCardIndex > 0) {
        showCard(currentCardIndex - 1);
    } else if (cards.length > 0) {
        showCard(cards.length - 1);
    }
}

// Card review functions
function reviewCard(correct) {
    if (!currentCard) return;

    const cardId = currentCard.id;
    fetch(`/api/cards/${cardId}/review`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ correct })
    })
    .then(response => {
        // Add explicit error handling for non-200 responses
        if (!response.ok) {
            return response.text().then(errorText => {
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
            });
        }
        return response.json();
    })
    .then(updatedCard => {
        // Update the card in our local array
        const index = cards.findIndex(c => c.id === cardId);
        if (index !== -1) {
            cards[index] = updatedCard;
        }
        
        // Update box stats and indicator
        updateBoxStats();
        updateBoxIndicator(updatedCard.box_number);
        
        // Show success message
        const message = correct ? 
            `Moved to Box ${updatedCard.box_number} - Next review in ${getIntervalText(updatedCard.box_number)}` :
            'Moved back to Box 1 - Review again tomorrow';
        showToast(message);
        
        // Move to next card
        showNextCard();
    })
    .catch(error => {
        console.error('Error reviewing card:', error);
        showToast(`Error reviewing card: ${error.message}`, 5000);
    });
}

function getIntervalText(boxNumber) {
    const intervals = {
        0: 'now',
        1: '1 day',
        2: '3 days',
        3: '10 days',
        4: '30 days',
        5: '90 days'
    };
    return intervals[boxNumber] || 'unknown';
}

// Card flipping with auto-pronunciation
function toggleFlip() {
    // Get card element with error checking
    const cardElement = document.getElementById('flashcard');
    const meaningElement = document.getElementById('meaning');
    const exampleElement = document.getElementById('example');
    const wordElement = document.getElementById('word');
    const ipaElement = document.getElementById('ipa');

    // Validate DOM elements
    const elementsToCheck = [
        { element: cardElement, name: 'flashcard' },
        { element: meaningElement, name: 'meaning' },
        { element: exampleElement, name: 'example' },
        { element: wordElement, name: 'word' },
        { element: ipaElement, name: 'ipa' }
    ];

    // Check if any required elements are missing
    const missingElements = elementsToCheck.filter(item => !item.element);
    if (missingElements.length > 0) {
        console.error('Missing DOM elements:', 
            missingElements.map(item => item.name).join(', '));
        showToast('Error flipping card. Check console.');
        return;
    }

    // Check if current card exists
    if (!currentCard) {
        console.error('No current card to flip');
        showToast('No card to display');
        return;
    }

    // Toggle card flip
    cardElement.classList.toggle('flipped');

    // Update content when flipping to back
    if (cardElement.classList.contains('flipped')) {
        // Populate back of card
        meaningElement.textContent = currentCard.meaning || 'No meaning available';
        exampleElement.textContent = currentCard.example || 'No example available';
        
        // Speak word if auto-speak is enabled
        if (autoSpeak) {
            speakWord();
        }
    } else {
        // Reset to initial state when flipping back
        meaningElement.textContent = 'Tap to reveal meaning';
        exampleElement.textContent = '';
    }
}

// Audio pronunciation
function speakWord() {
    if (!currentCard || !currentCard.word || isInitialLoad) return;
    
    // Use TTS API directly
    console.log('Speaking word:', currentCard.word);
    
    const ttsUrl = `/api/speak/${encodeURIComponent(currentCard.word)}?rate=${speechRate}`;
    console.log('Using TTS API:', ttsUrl);
    
    const audio = new Audio(ttsUrl);
    
    audio.onerror = function(error) {
        console.error('Audio error:', error);
        if (!isInitialLoad && document.visibilityState === 'visible') {
            showToast('Error playing pronunciation');
        }
    };
    
    audio.onloadeddata = function() {
        console.log('Audio loaded successfully');
    };
    
    audio.play()
        .then(() => {
            console.log('Playing audio');
        })
        .catch(error => {
            console.error('Error playing audio:', error);
            if (!isInitialLoad && document.visibilityState === 'visible') {
                showToast('Error playing pronunciation');
            }
        });
}

// YouTube import functionality
function importFromYouTube() {
    const urlInput = document.getElementById('youtubeUrl');
    const url = urlInput.value.trim();
    
    if (!url) {
        showToast('Please enter a YouTube URL');
        return;
    }
    
    showLoading(true);
    fetch('/api/youtube/import', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url })
    })
    .then(response => response.json())
    .then(data => {
        showToast(`Successfully imported ${data.imported} words`);
        urlInput.value = '';
        loadCards();
    })
    .catch(error => {
        console.error('Error importing from YouTube:', error);
        showToast('Error importing words from YouTube');
    })
    .finally(() => {
        showLoading(false);
    });
}

// UI helpers
function showLoading(show) {
    document.getElementById('loadingIndicator').classList.toggle('hidden', !show);
}

function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    
    toastMessage.textContent = message;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, duration);
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initialize box system
    updateBoxStats();
    setInterval(updateBoxStats, 60000); // Update stats every minute
    
    // Load initial cards
    loadCards();
    
    // Navigation buttons
    document.getElementById('prevBtn').addEventListener('click', showPreviousCard);
    document.getElementById('nextBtn').addEventListener('click', showNextCard);
    document.getElementById('flipBtn').addEventListener('click', toggleFlip);
    document.getElementById('flipBackBtn').addEventListener('click', toggleFlip);
    
    // Card action buttons
    document.getElementById('speakBtn').addEventListener('click', speakWord);
    document.getElementById('markLearnedBtn').addEventListener('click', () => reviewCard(true));
    document.getElementById('markReviewBtn').addEventListener('click', () => reviewCard(false));
    
    // Auto-speak setting
    const autoSpeakCheckbox = document.getElementById('autoSpeak');
    autoSpeakCheckbox.checked = localStorage.getItem('autoSpeak') === 'true';
    autoSpeak = autoSpeakCheckbox.checked;
    
    autoSpeakCheckbox.addEventListener('change', (e) => {
        autoSpeak = e.target.checked;
        localStorage.setItem('autoSpeak', autoSpeak);
        showToast(autoSpeak ? 'Auto-pronunciation enabled' : 'Auto-pronunciation disabled');
    });
    
    // Speech rate control
    const rateControl = document.getElementById('speechRate');
    const rateValue = document.getElementById('rateValue');
    if (rateControl && rateValue) {
        // Load saved rate or use default
        speechRate = parseFloat(localStorage.getItem('speechRate')) || 1.0;
        rateControl.value = speechRate;
        rateValue.textContent = `${speechRate}x`;
        
        rateControl.addEventListener('input', (e) => {
            speechRate = parseFloat(e.target.value);
            rateValue.textContent = `${speechRate}x`;
            localStorage.setItem('speechRate', speechRate);
            showToast(`Speech rate set to ${speechRate}x`);
        });
    }
    
    // YouTube import
    document.getElementById('importBtn').addEventListener('click', importFromYouTube);
    
    // Keyboard navigation
    document.addEventListener('keydown', (event) => {
        switch(event.key) {
            case 'ArrowLeft':
                showPreviousCard();
                break;
            case 'ArrowRight':
                showNextCard();
                break;
            case ' ':
                toggleFlip();
                event.preventDefault(); // Prevent page scroll
                break;
            case 'k':
                reviewCard(true); // Know this word
                break;
            case 'r':
                reviewCard(false); // Review again
                break;
            case 's':
                speakWord(); // Speak word
                break;
        }
    });
});