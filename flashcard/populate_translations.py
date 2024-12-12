import sqlite3
from googletrans import Translator

def populate_translations(db_path):
    translator = Translator()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch all words from the cards table
    cursor.execute('SELECT id, word FROM cards')
    rows = cursor.fetchall()
    
    for row in rows:
        id, word = row
        try:
            # Translate the word to Vietnamese
            translation = translator.translate(word, dest='vi').text
            # Update the database with the translation
            cursor.execute('UPDATE cards SET vietnamese_translation = ? WHERE id = ?', (translation, id))
        except Exception:
            # Leave the translation field empty if an error occurs
            print(f'Error translating word {word} (ID {id}): Translation failed, leaving it unchanged.')
    
    conn.commit()
    conn.close()
    print('Translations populated successfully.')

if __name__ == '__main__':
    populate_translations('flashcards.db')
