// Global variables
let cards = [];
let currentCardIndex = 0;
let currentCard = null;
let autoSpeak = false;

// Event listener for DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');
    const flashcards = [
        { front: "Hello", back: "Xin chào" },
        { front: "Goodbye", back: "Tạm biệt" },
        { front: "Thank you", back: "Cảm ơn" },
        { front: "Yes", back: "Có" },
        { front: "No", back: "Không" },
        { front: "Welcome", back: "Chào mừng" },
        { front: "Chào mừng", back: "Welcome" } // New flashcard added
    ];

    let currentIndex = 0;

    // Function to translate the word to Vietnamese, Chinese, and Japanese
    async function translateWord(word) {
        console.log(`Translating word: ${word}`);
        const response = await fetch(`https://api.example.com/translate?text=${word}&target=vi,zh,jp`);
        console.log(`Received response from translation API`);
        const data = await response.json();
        console.log(`Received translation data: ${JSON.stringify(data)}`);
        return {
            vietnamese: data.vietnamese_translation,
            chinese: data.chinese_translation,
            japanese: data.japanese_translation
        };
    }

    // Update flashcard display
    async function updateFlashcard(word) {
        console.log(`Updating flashcard with word: ${word}`);
        const translations = await translateWord(word);
        const translationElementVi = document.getElementById('back-word');
        const translationElementZh = document.getElementById('chinese-translation');
        const translationElementJp = document.getElementById('japanese-translation');

        if (translationElementVi) {
            translationElementVi.innerText = translations.vietnamese || 'Không có bản dịch';
        } else {
            console.error('Vietnamese translation element not found');
        }

        if (translationElementZh) {
            translationElementZh.innerText = translations.chinese || '没有翻译'; // "No translation" in Chinese
        } else {
            console.error('Chinese translation element not found');
        }

        if (translationElementJp) {
            translationElementJp.innerText = translations.japanese || '翻訳がありません'; // "No translation" in Japanese
        } else {
            console.error('Japanese translation element not found');
        }
    }

    async function displayFlashcard() {
        console.log(`Displaying flashcard at index: ${currentIndex}`);
        const frontWordElement = document.getElementById('front-word');
        const backWordElement = document.getElementById('back-word');

        if (frontWordElement && backWordElement) {
            frontWordElement.textContent = flashcards[currentIndex].front;
            await updateFlashcard(flashcards[currentIndex].front);
        } else {
            console.error('Front or back word element not found');
        }
    }

    const nextButton = document.getElementById('next-button');
    if (nextButton) {
        nextButton.addEventListener('click', async function() {
            currentIndex = (currentIndex + 1) % flashcards.length;
            await displayFlashcard();
        });
    } else {
        console.error('Next button not found');
    }

    const flashcardElement = document.querySelector('.flashcard');
    if (flashcardElement) {
        flashcardElement.addEventListener('click', function() {
            flipCard();
        });
    } else {
        console.error('Flashcard element not found');
    }

    function flipCard() {
        const card = document.querySelector('.flashcard');
        const englishWord = card.querySelector('#front-word');
        const vietnameseTranslation = card.querySelector('#back-word');

        if (card.classList.contains('flipped')) {
            card.classList.remove('flipped');
            englishWord.style.display = 'block';
            vietnameseTranslation.style.display = 'none';
        } else {
            card.classList.add('flipped');
            englishWord.style.display = 'none';
            vietnameseTranslation.style.display = 'block';
        }
    }

    // Initial display
    displayFlashcard();
});
