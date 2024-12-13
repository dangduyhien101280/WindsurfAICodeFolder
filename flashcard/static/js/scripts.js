document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed'); // Log when DOM is ready
    const flashcards = [
        { front: "Hello", back: "Xin chào" },
        { front: "Goodbye", back: "Tạm biệt" },
        { front: "Thank you", back: "Cảm ơn" },
        { front: "Yes", back: "Có" },
        { front: "No", back: "Không" }
    ];

    let currentIndex = 0;

    // Function to translate the word to Vietnamese
    async function translateToVietnamese(word) {
        console.log(`Translating word: ${word}`); // Log translation attempt
        const response = await fetch(`https://api.example.com/translate?text=${word}&target=vi`);
        console.log(`Received response from translation API`); // Log API response
        const data = await response.json();
        console.log(`Received translation data: ${data.translation}`); // Log translation data
        return data.translation;
    }

    // Update flashcard display
    async function updateFlashcard(word) {
        console.log(`Updating flashcard with word: ${word}`); // Log flashcard update attempt
        const translation = await translateToVietnamese(word);
        const translationElement = document.getElementById('back-word');
        if (translationElement) {
            console.log(`Found translation element, updating text`); // Log translation element found
            translationElement.innerText = translation;
        } else {
            console.error('Translation element not found'); // Log translation element not found
        }
    }

    async function displayFlashcard() {
        console.log(`Displaying flashcard at index: ${currentIndex}`); // Log flashcard display attempt
        const frontWordElement = document.getElementById('front-word');
        const backWordElement = document.getElementById('back-word');

        if (frontWordElement && backWordElement) {
            console.log(`Found front and back word elements, updating text`); // Log front and back word elements found
            frontWordElement.textContent = flashcards[currentIndex].front;
            const translation = await translateToVietnamese(flashcards[currentIndex].front);
            backWordElement.textContent = translation; // Update back with translation
        } else {
            console.error('Front or back word element not found'); // Log front or back word element not found
        }
    }

    const nextButton = document.getElementById('next-button');
    if (nextButton) {
        console.log(`Found next button, adding event listener`); // Log next button found
        nextButton.addEventListener('click', async function() {
            console.log(`Next button clicked, incrementing index`); // Log next button click
            currentIndex = (currentIndex + 1) % flashcards.length; // Cycle through flashcards
            await displayFlashcard();
        });
    } else {
        console.error('Next button not found'); // Log next button not found
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

        console.log('Flipping card. Current state:', card.classList.contains('flipped'));
        console.log('English Word:', englishWord.textContent);
        console.log('Vietnamese Translation:', vietnameseTranslation.textContent);

        // Logic to flip the card
        if (card.classList.contains('flipped')) {
            card.classList.remove('flipped');
            englishWord.style.display = 'block';
            vietnameseTranslation.style.display = 'none';
        } else {
            card.classList.add('flipped');
            englishWord.style.display = 'none';
            vietnameseTranslation.style.display = 'block'; // Show the Vietnamese translation
        }
    }

    // Initial display
    console.log(`Displaying initial flashcard`); // Log initial flashcard display
    displayFlashcard();
});
