// State management
let cards = [];
let currentCardIndex = 0;

// Fetch cards from the server
async function fetchCards() {
    try {
        const response = await fetch('/api/cards');
        cards = await response.json();
        if (cards.length > 0) {
            updateCard();
            updateProgress();
        } else {
            showEmptyState();
        }
    } catch (error) {
        console.error('Error fetching cards:', error);
        showError('Failed to load flashcards');
    }
}

// Update the card content
function updateCard() {
    if (cards.length === 0) return;
    
    const card = cards[currentCardIndex];
    document.getElementById('word').textContent = card.word;
    document.getElementById('ipa').textContent = card.ipa || '';
    document.getElementById('meaning').textContent = card.meaning;
    document.getElementById('example').textContent = card.example;
    
    // Update learned status
    const flashcard = document.getElementById('flashcard');
    flashcard.classList.toggle('learned', card.learned);
    
    // Update next review date
    const studyDate = document.getElementById('studyDate');
    if (card.next_review) {
        const reviewDate = new Date(card.next_review);
        studyDate.textContent = `Next Review: ${reviewDate.toLocaleDateString()}`;
    } else {
        studyDate.textContent = 'Next Review: Not scheduled';
    }
    
    // Add animation
    flashcard.classList.add('new-word');
    setTimeout(() => flashcard.classList.remove('new-word'), 500);
}

// Update progress display
function updateProgress() {
    document.getElementById('currentCard').textContent = currentCardIndex + 1;
    document.getElementById('totalCards').textContent = cards.length;
    
    // Update learned count
    const learnedCount = cards.filter(card => card.learned).length;
    document.getElementById('learned').textContent = learnedCount;
    document.getElementById('total').textContent = cards.length;
}

// Card navigation functions
function nextCard() {
    if (currentCardIndex < cards.length - 1) {
        currentCardIndex++;
        updateCard();
        updateProgress();
        resetCardFlip();
    }
}

function previousCard() {
    if (currentCardIndex > 0) {
        currentCardIndex--;
        updateCard();
        updateProgress();
        resetCardFlip();
    }
}

function resetCardFlip() {
    document.getElementById('flashcard').classList.remove('flipped');
}

function toggleCardFlip() {
    document.getElementById('flashcard').classList.toggle('flipped');
}

// Audio playback
async function speakWord() {
    const word = cards[currentCardIndex].word;
    try {
        const audio = new Audio(`/api/speak/${encodeURIComponent(word)}`);
        await audio.play();
    } catch (error) {
        console.error('Error playing audio:', error);
        showError('Failed to play pronunciation');
    }
}

// Card status management
async function markLearned() {
    const card = cards[currentCardIndex];
    try {
        const response = await fetch(`/api/mark-learned/${card.id}`, { method: 'POST' });
        if (response.ok) {
            card.learned = true;
            updateCard();
            updateProgress();
            showSuccess('Card marked as learned');
        }
    } catch (error) {
        console.error('Error marking card as learned:', error);
        showError('Failed to mark card as learned');
    }
}

async function scheduleReview() {
    const card = cards[currentCardIndex];
    try {
        const response = await fetch(`/api/schedule-review/${card.id}`, { method: 'POST' });
        if (response.ok) {
            await fetchCards(); // Refresh cards to get updated review date
            showSuccess('Review scheduled');
        }
    } catch (error) {
        console.error('Error scheduling review:', error);
        showError('Failed to schedule review');
    }
}

// YouTube import functionality
async function importFromYoutube() {
    const urlInput = document.getElementById('youtubeUrl');
    const url = urlInput.value.trim();
    
    if (!url) {
        showError('Please enter a YouTube URL');
        return;
    }
    
    try {
        const response = await fetch('/api/import-youtube', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        const result = await response.json();
        if (result.success) {
            showSuccess(`Successfully added ${result.words_added} new words!`);
            urlInput.value = '';
            await fetchCards();
        } else {
            showError(result.error || 'Failed to import words');
        }
    } catch (error) {
        console.error('Error importing from YouTube:', error);
        showError('Error importing words from YouTube');
    }
}

// UI feedback functions
function showSuccess(message) {
    // You can implement a toast or notification system here
    console.log('Success:', message);
}

function showError(message) {
    // You can implement a toast or notification system here
    console.error('Error:', message);
}

function showEmptyState() {
    document.getElementById('word').textContent = 'No cards available';
    document.getElementById('ipa').textContent = '';
    document.getElementById('meaning').textContent = 'Import some words to get started';
    document.getElementById('example').textContent = '';
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Card navigation
    document.getElementById('prevBtn').addEventListener('click', previousCard);
    document.getElementById('nextBtn').addEventListener('click', nextCard);
    document.getElementById('flipBtn').addEventListener('click', toggleCardFlip);
    
    // Card actions
    document.getElementById('speakBtn').addEventListener('click', (e) => {
        e.stopPropagation();
        speakWord();
    });
    
    document.getElementById('markLearnedBtn').addEventListener('click', (e) => {
        e.stopPropagation();
        markLearned();
    });
    
    document.getElementById('markReviewBtn').addEventListener('click', (e) => {
        e.stopPropagation();
        scheduleReview();
    });
    
    // Card flip on click
    document.getElementById('flashcard').addEventListener('click', toggleCardFlip);
    
    // YouTube import
    document.getElementById('importBtn').addEventListener('click', importFromYoutube);
    
    // Initialize
    fetchCards();
});