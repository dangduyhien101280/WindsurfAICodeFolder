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
        flashcardElement.addEventListener('click', async function() {
            this.classList.toggle('flipped');
            if (this.classList.contains('flipped')) {
                const cardId = currentIndex; // Ensure currentIndex corresponds to the card ID
                console.log('Fetching translation for card ID:', cardId);
                const response = await fetch(`/get_translation/${cardId}`);
                console.log('Response status:', response.status);
                if (response.ok) {
                    const data = await response.json();
                    console.log('Translation data received:', data);
                    const backWordElement = document.getElementById('back-word');
                    if (backWordElement) {
                        backWordElement.textContent = data.translation; // Update the back with translation
                        console.log('Translation displayed:', data.translation);
                    } else {
                        console.error('Back word element not found');
                    }
                } else {
                    console.error('Failed to fetch translation:', response.statusText);
                }
            }
        });
    } else {
        console.error('Flashcard element not found');
    }

    // Initial display
    console.log(`Displaying initial flashcard`); // Log initial flashcard display
    displayFlashcard();
});
