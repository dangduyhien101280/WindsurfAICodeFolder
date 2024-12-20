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
    const cardNumberElement = document.getElementById('card-number');  // Card number element
    const boxNumberElement = document.getElementById('box-number');  // Box number element
    const cardNumberBackElement = document.getElementById('card-number-back');  // Card number back element
    const boxNumberBackElement = document.getElementById('box-number-back');  // Box number back element

    // Validate DOM elements
    const elementsToCheck = [
        { element: cardElement, name: 'flashcard' },
        { element: wordElement, name: 'word' },
        { element: meaningElement, name: 'meaning' },
        { element: exampleElement, name: 'example' },
        { element: ipaElement, name: 'ipa' },
        { element: posElement, name: 'pos' },
        { element: cardNumberElement, name: 'card-number' },
        { element: boxNumberElement, name: 'box-number' },
        { element: cardNumberBackElement, name: 'card-number-back' },
        { element: boxNumberBackElement, name: 'box-number-back' }
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

    // Update card number on both sides
    const cardNumberText = `${currentCardIndex + 1}/${cards.length}`;
    cardNumberElement.textContent = cardNumberText;
    cardNumberBackElement.textContent = cardNumberText;

    // Update box number on both sides
    const boxNumberText = `Box: ${currentCard.box_number}`;
    boxNumberElement.textContent = boxNumberText;
    boxNumberBackElement.textContent = boxNumberText;

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
    const loadingSpinner = document.getElementById('loading-spinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = show ? 'flex' : 'none';
    }
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

// Comprehensive Learning Data Management
const LearningDataManager = {
    // Key for storing learning data in local storage
    STORAGE_KEY: 'flashcard_learning_data',

    // Collect comprehensive learning data
    collectLearningData() {
        try {
            return {
                metadata: this.collectMetadata(),
                progress: this.collectProgressData(),
                studyStatistics: this.collectStudyStatistics(),
                achievements: this.collectAchievements(),
                learningGoals: this.collectLearningGoals(),
                flashcardDetails: this.collectFlashcardDetails(),
                boxSystemProgress: this.collectBoxSystemProgress()
            };
        } catch (error) {
            console.error('Error collecting learning data:', error);
            return null;
        }
    },

    // Collect basic metadata
    collectMetadata() {
        return {
            timestamp: new Date().toISOString(),
            appVersion: '1.0.0',
            environment: navigator.userAgent
        };
    },

    // Collect overall progress data
    collectProgressData() {
        const totalCards = parseInt(document.getElementById('total').textContent) || 0;
        const learnedCards = parseInt(document.getElementById('learned').textContent) || 0;
        
        return {
            totalCards: totalCards,
            learnedCards: learnedCards,
            progressPercentage: totalCards > 0 ? ((learnedCards / totalCards) * 100).toFixed(2) : 0
        };
    },

    // Collect detailed study statistics
    collectStudyStatistics() {
        return {
            totalStudyTime: localStorage.getItem('total_study_time') || '0 minutes',
            lastStudySession: localStorage.getItem('last_study_session') || 'N/A',
            studySessionsCount: parseInt(localStorage.getItem('study_sessions_count') || '0'),
            averageStudyTimePerSession: this.calculateAverageStudyTime()
        };
    },

    // Calculate average study time
    calculateAverageStudyTime() {
        const totalTime = localStorage.getItem('total_study_time') || '0';
        const sessionCount = parseInt(localStorage.getItem('study_sessions_count') || '1');
        
        // Parse time string (assuming format like "45 minutes")
        const timeValue = parseInt(totalTime.split(' ')[0]);
        return (timeValue / sessionCount).toFixed(2) + ' minutes';
    },

    // Collect achievements
    collectAchievements() {
        // This would ideally come from a backend or more persistent storage
        return [
            { 
                name: 'Vocabulary Novice', 
                description: 'Learned first 50 words',
                status: 'Completed',
                dateAchieved: localStorage.getItem('vocabulary_novice_date') || 'N/A'
            },
            { 
                name: 'Language Explorer', 
                description: 'Study for 7 consecutive days',
                status: 'In Progress',
                progress: localStorage.getItem('language_explorer_progress') || '3/7 days'
            }
        ];
    },

    // Collect learning goals
    collectLearningGoals() {
        return [
            { 
                goal: 'Learn 500 Vocabulary Words', 
                progress: localStorage.getItem('vocabulary_goal_progress') || 250,
                total: 500,
                deadline: localStorage.getItem('vocabulary_goal_deadline') || 'No deadline set'
            },
            { 
                goal: 'Complete Grammar Course', 
                progress: localStorage.getItem('grammar_goal_progress') || 3,
                total: 10,
                deadline: localStorage.getItem('grammar_goal_deadline') || 'No deadline set'
            }
        ];
    },

    // Collect flashcard details
    collectFlashcardDetails() {
        // This would ideally come from a more comprehensive tracking system
        return {
            difficultWords: this.getDifficultWords(),
            recentlyLearnedWords: this.getRecentlyLearnedWords()
        };
    },

    // Get list of difficult words
    getDifficultWords() {
        // Simulated difficult words tracking
        return JSON.parse(localStorage.getItem('difficult_words') || '[]');
    },

    // Get recently learned words
    getRecentlyLearnedWords() {
        // Simulated recently learned words
        return JSON.parse(localStorage.getItem('recently_learned_words') || '[]');
    },

    // Collect box system progress
    collectBoxSystemProgress() {
        const boxProgress = [];
        const boxElements = document.querySelectorAll('.box');
        
        boxElements.forEach(box => {
            const boxNumber = box.getAttribute('data-box');
            const boxCount = box.querySelector('.box-count').textContent;
            
            boxProgress.push({
                boxNumber: boxNumber,
                cardCount: parseInt(boxCount)
            });
        });

        return boxProgress;
    },

    // Export learning data
    exportLearningData() {
        try {
            // Collect comprehensive learning data
            const learningData = this.collectLearningData();
            
            if (!learningData) {
                throw new Error('Failed to collect learning data');
            }

            // Convert data to JSON string with pretty printing
            const exportData = JSON.stringify(learningData, null, 2);

            // Create a Blob with the data
            const blob = new Blob([exportData], { type: 'application/json' });

            // Create a download link
            const downloadLink = document.createElement('a');
            downloadLink.href = URL.createObjectURL(blob);
            
            // Generate filename with current date and timestamp
            const now = new Date();
            const filename = `learning_data_${now.toISOString().replace(/:/g, '-').split('.')[0]}.json`;
            downloadLink.download = filename;

            // Trigger download
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);

            // Save to local storage as backup
            localStorage.setItem(this.STORAGE_KEY, exportData);
            localStorage.setItem(`${this.STORAGE_KEY}_timestamp`, now.toISOString());

            // Show success toast
            showToast('Learning data exported successfully!', 'success');

            return true;
        } catch (error) {
            console.error('Error exporting learning data:', error);
            showToast('Failed to export learning data. Please try again.', 'error');
            return false;
        }
    },

    // Import learning data
    importLearningData(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (event) => {
                try {
                    const importedData = JSON.parse(event.target.result);
                    
                    // Validate imported data structure
                    if (!importedData.metadata || !importedData.progress) {
                        throw new Error('Invalid learning data format');
                    }

                    // Restore data to local storage
                    this.restoreLearningData(importedData);

                    showToast('Learning data imported successfully!', 'success');
                    resolve(importedData);
                } catch (error) {
                    console.error('Error importing learning data:', error);
                    showToast('Failed to import learning data. Please check the file.', 'error');
                    reject(error);
                }
            };

            reader.onerror = (error) => {
                console.error('File reading error:', error);
                showToast('Error reading file. Please try again.', 'error');
                reject(error);
            };

            reader.readAsText(file);
        });
    },

    // Restore learning data to local storage
    restoreLearningData(data) {
        // Restore progress data
        if (data.progress) {
            localStorage.setItem('total_cards', data.progress.totalCards);
            localStorage.setItem('learned_cards', data.progress.learnedCards);
        }

        // Restore study statistics
        if (data.studyStatistics) {
            localStorage.setItem('total_study_time', data.studyStatistics.totalStudyTime);
            localStorage.setItem('last_study_session', data.studyStatistics.lastStudySession);
            localStorage.setItem('study_sessions_count', data.studyStatistics.studySessionsCount);
        }

        // Restore achievements and goals (simplified)
        if (data.achievements) {
            localStorage.setItem('achievements', JSON.stringify(data.achievements));
        }

        if (data.learningGoals) {
            localStorage.setItem('learning_goals', JSON.stringify(data.learningGoals));
        }

        // Optionally, trigger UI update
        this.updateUIAfterImport(data);
    },

    // Update UI after data import
    updateUIAfterImport(data) {
        // Update total and learned cards
        if (data.progress) {
            const totalElement = document.getElementById('total');
            const learnedElement = document.getElementById('learned');
            
            if (totalElement) totalElement.textContent = data.progress.totalCards;
            if (learnedElement) learnedElement.textContent = data.progress.learnedCards;
        }

        // Update box system progress
        if (data.boxSystemProgress) {
            const boxElements = document.querySelectorAll('.box');
            
            data.boxSystemProgress.forEach(boxData => {
                const boxElement = Array.from(boxElements).find(
                    el => el.getAttribute('data-box') === boxData.boxNumber.toString()
                );
                
                if (boxElement) {
                    const countElement = boxElement.querySelector('.box-count');
                    if (countElement) countElement.textContent = boxData.cardCount;
                }
            });
        }
    }
};

// Event Listeners for Export and Import
document.addEventListener('DOMContentLoaded', function() {
    const exportButton = document.getElementById('exportDataBtn');
    const importButton = document.getElementById('importDataBtn');
    const importFileInput = document.getElementById('importFileInput');

    if (exportButton) {
        exportButton.addEventListener('click', () => {
            LearningDataManager.exportLearningData();
        });
    }

    if (importButton && importFileInput) {
        importButton.addEventListener('click', () => {
            importFileInput.click();
        });

        importFileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                LearningDataManager.importLearningData(file)
                    .then(() => {
                        // Optional: additional actions after successful import
                        event.target.value = ''; // Clear the file input
                    })
                    .catch(error => {
                        console.error('Import failed:', error);
                    });
            }
        });
    }
});

// Data Export Functionality
function exportLearningData() {
    try {
        // Collect learning data from various sources
        const learningData = {
            timestamp: new Date().toISOString(),
            totalCards: document.getElementById('total').textContent,
            learnedCards: document.getElementById('learned').textContent,
            progress: calculateProgress(),
            studyStats: collectStudyStatistics(),
            achievements: collectAchievements(),
            goals: collectLearningGoals()
        };

        // Convert data to JSON string
        const exportData = JSON.stringify(learningData, null, 2);

        // Create a Blob with the data
        const blob = new Blob([exportData], { type: 'application/json' });

        // Create a download link
        const downloadLink = document.createElement('a');
        downloadLink.href = URL.createObjectURL(blob);
        
        // Generate filename with current date
        const filename = `learning_data_${new Date().toISOString().split('T')[0]}.json`;
        downloadLink.download = filename;

        // Trigger download
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);

        // Optional: Save to local storage as backup
        localStorage.setItem('flashcard_learning_data', exportData);

        // Show success toast
        showToast('Learning data exported successfully!');
    } catch (error) {
        console.error('Error exporting learning data:', error);
        showToast('Failed to export learning data. Please try again.');
    }
}

function calculateProgress() {
    const total = parseInt(document.getElementById('total').textContent);
    const learned = parseInt(document.getElementById('learned').textContent);
    return total > 0 ? ((learned / total) * 100).toFixed(2) : 0;
}

function collectStudyStatistics() {
    // Collect study-related statistics
    return {
        studyTime: localStorage.getItem('total_study_time') || '0 minutes',
        lastStudySession: localStorage.getItem('last_study_session') || 'N/A',
        studySessions: localStorage.getItem('study_sessions_count') || 0
    };
}

function collectAchievements() {
    // Simulated achievements collection
    return [
        { name: 'Vocabulary Novice', status: 'Completed' },
        { name: 'Language Explorer', status: 'In Progress' }
    ];
}

function collectLearningGoals() {
    // Simulated learning goals collection
    return [
        { 
            goal: 'Learn 500 Vocabulary Words', 
            progress: 250, 
            total: 500 
        },
        { 
            goal: 'Complete Grammar Course', 
            progress: 3, 
            total: 10 
        }
    ];
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
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
    
    // Điều hướng tới trang User Profile
    const userProfileButton = document.getElementById('userProfileBtn');
    
    if (userProfileButton) {
        userProfileButton.addEventListener('click', function(event) {
            event.preventDefault();
            
            // Hiển thị trạng thái tải
            showLoading(true);
            
            fetch('/user_profile', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Kiểm tra lỗi từ server
                if (data.error) {
                    throw new Error(data.message || 'Lỗi không xác định');
                }
                
                // Tạo HTML từ dữ liệu JSON
                const profileHtml = `
                    <div class="user-profile-container">
                        <div class="profile-header">
                            <a href="/" class="btn btn-secondary back-btn mb-3">
                                <i class="fas fa-arrow-left"></i> Quay lại
                            </a>

                            <div class="text-center">
                                <img src="/static/images/default-avatar.png" alt="Avatar" class="profile-avatar">
                                <h1>${data.full_name}</h1>
                                <p class="username text-muted">@${data.username}</p>
                            </div>

                            <div class="profile-stats row g-3 mb-4">
                                <div class="col-md-4">
                                    <div class="stat-card">
                                        <h3>Từ Vựng</h3>
                                        <p class="stat-number">${data.total_words}</p>
                                        <small>Từ đã học</small>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="stat-card">
                                        <h3>Thời Gian Học</h3>
                                        <p class="stat-number">${data.study_time} giờ</p>
                                        <small>Tổng thời gian học</small>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="stat-card">
                                        <h3>Điểm Thành Tích</h3>
                                        <p class="stat-number">${data.achievement_points}</p>
                                        <small>Tổng điểm</small>
                                    </div>
                                </div>
                            </div>

                            <div class="profile-details row g-3">
                                <div class="col-md-6">
                                    <div class="detail-card">
                                        <h3>Thông Tin Cá Nhân</h3>
                                        <p><strong>Email:</strong> ${data.email}</p>
                                        <p><strong>Trình Độ:</strong> ${data.language_level}</p>
                                        <p><strong>Mục Tiêu Học Tập:</strong> ${data.learning_goal}</p>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="detail-card">
                                        <h3>Thành Tích</h3>
                                        <div class="streak-info">
                                            <p><strong>Chuỗi Học Tập Hiện Tại:</strong> ${data.current_streak} ngày</p>
                                            <p><strong>Chuỗi Học Tập Cao Nhất:</strong> ${data.max_streak} ngày</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="recent-achievements mt-4">
                                <h3>Thành Tích Gần Đây</h3>
                                ${data.recent_achievements.length > 0 ? `
                                    <div class="achievements-list">
                                        ${data.recent_achievements.map(achievement => `
                                            <div class="achievement-item">
                                                <h4>${achievement.name}</h4>
                                                <p>${achievement.description}</p>
                                                <small>+${achievement.points} điểm | ${achievement.date}</small>
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : `
                                    <p class="text-muted">Chưa có thành tích nào.</p>
                                `}
                            </div>
                        </div>
                    </div>
                `;
                
                // Thay thế nội dung của phần tử main-content
                const existingMainContent = document.querySelector('.main-content');
                if (existingMainContent) {
                    existingMainContent.innerHTML = profileHtml;
                    console.log('User profile content updated successfully');
                } else {
                    console.error('Không tìm thấy phần tử .main-content để thay thế');
                    throw new Error('Không tìm thấy phần tử .main-content để thay thế');
                }
                
                // Ẩn trạng thái tải
                showLoading(false);
            })
            .catch(error => {
                console.error('Chi tiết lỗi:', error);
                
                // Hiển thị thông báo lỗi chi tiết
                alert(`Không thể tải trang hồ sơ. Chi tiết: ${error.message}`);
                
                // Ẩn trạng thái tải
                showLoading(false);
            });
        });
    }
});

// Xử lý Avatar Modal
document.addEventListener('DOMContentLoaded', function() {
    const avatarFileInput = document.querySelector('#avatarModal input[type="file"]');
    const avatarPreviewContainer = document.querySelector('#avatarModal .preview-container');
    const avatarSaveButton = document.querySelector('#avatarModal .btn-primary');

    avatarFileInput.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                avatarPreviewContainer.innerHTML = `
                    <img src="${e.target.result}" 
                         style="max-width: 250px; max-height: 250px; border-radius: 50%;">
                `;
            };
            reader.readAsDataURL(file);
        }
    });

    avatarSaveButton.addEventListener('click', function() {
        const file = avatarFileInput.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('avatar', file);

            fetch('/upload_avatar', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Cập nhật ảnh đại diện
                    document.querySelector('.profile-avatar').src = data.avatar_url;
                    bootstrap.Modal.getInstance(document.getElementById('avatarModal')).hide();
                } else {
                    alert('Lỗi: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Lỗi:', error);
                alert('Có lỗi xảy ra khi tải ảnh lên');
            });
        }
    });
});

// Xử lý Edit Profile Modal
document.addEventListener('DOMContentLoaded', function() {
    const editProfileModal = document.getElementById('editProfileModal');
    const saveProfileButton = editProfileModal.querySelector('.btn-primary');

    saveProfileButton.addEventListener('click', function() {
        const fullName = editProfileModal.querySelector('input[type="text"]').value;
        const languageLevel = editProfileModal.querySelector('.form-select').value;
        const learningGoal = editProfileModal.querySelector('textarea').value;

        const profileData = {
            full_name: fullName,
            language_level: languageLevel,
            learning_goal: learningGoal
        };

        fetch('/update_profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(profileData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Cập nhật thông tin trên trang
                document.querySelector('.profile-header h1').textContent = fullName;
                
                const personalDetailsCard = document.querySelector('.profile-details-card .card-body');
                personalDetailsCard.querySelector('p:nth-child(2)').innerHTML = `<strong>Trình Độ:</strong> ${languageLevel}`;
                personalDetailsCard.querySelector('p:nth-child(3)').innerHTML = `<strong>Mục Tiêu Học Tập:</strong> ${learningGoal}`;

                bootstrap.Modal.getInstance(editProfileModal).hide();
            } else {
                alert('Lỗi: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Lỗi:', error);
            alert('Có lỗi xảy ra khi cập nhật hồ sơ');
        });
    });
});

// Add event listener for user login button
const userLoginBtn = document.getElementById('userLoginBtn');
if (userLoginBtn) {
    userLoginBtn.addEventListener('click', function(event) {
        event.preventDefault();
        
        // Show loading state
        showLoading(true);
        
        // Navigate to user interface
        fetch('/user_interface', { method: 'GET' })
            .then(response => response.text())
            .then(html => {
                // Replace main content with user interface HTML
                const mainContent = document.querySelector('.main-content');
                if (mainContent) {
                    mainContent.innerHTML = html;
                    console.log('Navigated to user interface successfully');
                } else {
                    console.error('Could not find .main-content element');
                }
            })
            .catch(error => {
                console.error('Error navigating to user interface:', error);
                showToast('Failed to load user interface');
            })
            .finally(() => {
                showLoading(false);
            });
    });
}

// Add event listener for export button
document.addEventListener('DOMContentLoaded', function() {
    const exportButton = document.getElementById('exportDataBtn');
    if (exportButton) {
        exportButton.addEventListener('click', exportLearningData);
    }
});

// Data Export and Import Functionality
document.addEventListener('DOMContentLoaded', function() {
    const exportDataBtn = document.getElementById('exportdataBtn');
    const importDataBtn = document.getElementById('importdataBtn');
    const importFileInput = document.getElementById('importFile');

    // Export Data Button Event Listener
    if (exportDataBtn) {
        exportDataBtn.addEventListener('click', function() {
            try {
                // Collect comprehensive learning data
                const learningData = {
                    timestamp: new Date().toISOString(),
                    vocabularyCards: collectVocabularyData(),
                    studyProgress: collectStudyProgress(),
                    learningBoxes: collectLearningBoxes(),
                    achievements: collectAchievements()
                };

                // Convert data to JSON string
                const exportData = JSON.stringify(learningData, null, 2);

                // Create a Blob with the data
                const blob = new Blob([exportData], { type: 'application/json' });

                // Create a download link
                const downloadLink = document.createElement('a');
                downloadLink.href = URL.createObjectURL(blob);
                
                // Generate filename with current date
                const now = new Date();
                const filename = `flashcard_learning_data_${now.toISOString().split('T')[0]}.json`;
                downloadLink.download = filename;

                // Trigger download
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);

                // Optional: Save to local storage
                localStorage.setItem('flashcard_learning_backup', exportData);
                localStorage.setItem('flashcard_learning_backup_timestamp', now.toISOString());

                // Show success toast
                showToast('Learning data exported successfully!', 'success');
            } catch (error) {
                console.error('Export failed:', error);
                showToast('Failed to export data. Please try again.', 'error');
            }
        });
    }

    // Import Data Button Event Listener
    if (importDataBtn) {
        importDataBtn.addEventListener('click', function() {
            // Trigger file input click
            importFileInput.click();
        });
    }

    // File Input Change Event Listener
    if (importFileInput) {
        importFileInput.addEventListener('change', function(event) {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    try {
                        const importedData = JSON.parse(e.target.result);
                        
                        // Validate imported data
                        if (!importedData.timestamp || !importedData.vocabularyCards) {
                            throw new Error('Invalid data format');
                        }

                        // Restore vocabulary cards
                        if (importedData.vocabularyCards) {
                            restoreVocabularyData(importedData.vocabularyCards);
                        }

                        // Restore study progress
                        if (importedData.studyProgress) {
                            restoreStudyProgress(importedData.studyProgress);
                        }

                        // Restore learning boxes
                        if (importedData.learningBoxes) {
                            restoreLearningBoxes(importedData.learningBoxes);
                        }

                        // Restore achievements
                        if (importedData.achievements) {
                            restoreAchievements(importedData.achievements);
                        }

                        // Show success toast
                        showToast('Learning data imported successfully!', 'success');

                        // Optional: Refresh UI
                        updateUIAfterImport();
                    } catch (error) {
                        console.error('Import failed:', error);
                        showToast('Failed to import data. Please check the file.', 'error');
                    }
                };

                reader.onerror = function(error) {
                    console.error('File reading error:', error);
                    showToast('Error reading file. Please try again.', 'error');
                };

                // Read the file
                reader.readAsText(file);
            }
        });
    }

    // Helper function to collect vocabulary data
    function collectVocabularyData() {
        // Collect current vocabulary cards from local storage or current state
        const vocabularyCards = JSON.parse(localStorage.getItem('vocabulary_cards') || '[]');
        return vocabularyCards;
    }

    // Helper function to collect study progress
    function collectStudyProgress() {
        return {
            totalCards: parseInt(document.getElementById('total').textContent) || 0,
            learnedCards: parseInt(document.getElementById('learned').textContent) || 0,
            studyTime: localStorage.getItem('total_study_time') || '0 minutes',
            lastStudySession: localStorage.getItem('last_study_session') || 'N/A'
        };
    }

    // Helper function to collect learning boxes progress
    function collectLearningBoxes() {
        const boxProgress = [];
        const boxElements = document.querySelectorAll('.box');
        
        boxElements.forEach(box => {
            const boxNumber = box.getAttribute('data-box');
            const boxCount = box.querySelector('.box-count').textContent;
            
            boxProgress.push({
                boxNumber: boxNumber,
                cardCount: parseInt(boxCount)
            });
        });

        return boxProgress;
    }

    // Helper function to collect achievements
    function collectAchievements() {
        // Simulated achievements collection
        return [
            { 
                name: 'Vocabulary Novice', 
                status: localStorage.getItem('vocabulary_novice_status') || 'Not Completed'
            },
            { 
                name: 'Language Explorer', 
                status: localStorage.getItem('language_explorer_status') || 'Not Completed'
            }
        ];
    }

    // Helper function to restore vocabulary data
    function restoreVocabularyData(vocabularyCards) {
        // Store imported vocabulary cards in local storage
        localStorage.setItem('vocabulary_cards', JSON.stringify(vocabularyCards));
    }

    // Helper function to restore study progress
    function restoreStudyProgress(studyProgress) {
        // Update total and learned cards in UI
        const totalElement = document.getElementById('total');
        const learnedElement = document.getElementById('learned');
        
        if (totalElement) totalElement.textContent = studyProgress.totalCards;
        if (learnedElement) learnedElement.textContent = studyProgress.learnedCards;

        // Restore other study-related data
        localStorage.setItem('total_study_time', studyProgress.studyTime);
        localStorage.setItem('last_study_session', studyProgress.lastStudySession);
    }

    // Helper function to restore learning boxes
    function restoreLearningBoxes(boxProgress) {
        const boxElements = document.querySelectorAll('.box');
        
        boxProgress.forEach(boxData => {
            const boxElement = Array.from(boxElements).find(
                el => el.getAttribute('data-box') === boxData.boxNumber.toString()
            );
            
            if (boxElement) {
                const countElement = boxElement.querySelector('.box-count');
                if (countElement) countElement.textContent = boxData.cardCount;
            }
        });
    }

    // Helper function to restore achievements
    function restoreAchievements(achievements) {
        achievements.forEach(achievement => {
            localStorage.setItem(`${achievement.name.toLowerCase().replace(' ', '_')}_status`, achievement.status);
        });
    }

    // Update UI after import
    function updateUIAfterImport() {
        // Trigger any necessary UI updates or refreshes
        // This could include reloading flashcards, updating progress bars, etc.
        console.log('UI updated after data import');
    }
});