// Global variables
let cards = [];
let currentCardIndex = 0;
let currentCard = null;

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
                showCard(0);
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
    if (cards.length === 0) return;
    
    currentCardIndex = index;
    currentCard = cards[index];
    
    document.getElementById('word').textContent = currentCard.word;
    document.getElementById('meaning').textContent = currentCard.meaning || '';
    document.getElementById('example').textContent = currentCard.example || '';
    document.getElementById('ipa').textContent = currentCard.ipa || '';
    
    // Update box indicator
    updateBoxIndicator(currentCard.box_number);
    
    // Update next review date
    const nextReview = currentCard.next_review ? new Date(currentCard.next_review) : null;
    document.getElementById('studyDate').textContent = nextReview ? 
        `Next Review: ${nextReview.toLocaleDateString()}` : 
        'Next Review: Not scheduled';
        
    // Update progress
    document.getElementById('currentCard').textContent = index + 1;
    
    // Add new-word animation
    const wordElement = document.getElementById('word');
    wordElement.classList.remove('new-word');
    void wordElement.offsetWidth; // Trigger reflow
    wordElement.classList.add('new-word');
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
    .then(response => response.json())
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
        showToast('Error updating card progress');
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

// Card flipping
function toggleFlip() {
    const flashcard = document.getElementById('flashcard');
    flashcard.classList.toggle('flipped');
}

// Audio pronunciation
function speakWord() {
    if (!currentCard) return;
    
    const audio = new Audio(`/api/speak/${currentCard.word}`);
    audio.play().catch(error => {
        console.error('Error playing audio:', error);
        showToast('Error playing pronunciation');
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
    
    // Card action buttons
    document.getElementById('speakBtn').addEventListener('click', speakWord);
    document.getElementById('markLearnedBtn').addEventListener('click', () => reviewCard(true));
    document.getElementById('markReviewBtn').addEventListener('click', () => reviewCard(false));
    
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
                break;
        }
    });
});