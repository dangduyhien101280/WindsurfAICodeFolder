import sqlite3
import sys
import io
from colorama import init, Fore
from flask import Flask, render_template, jsonify

# Set the encoding for stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)

def check_cards():
    connection = sqlite3.connect('flashcards.db')
    cursor = connection.cursor()
    
    cursor.execute('SELECT word, vietnamese_translation, chinese, japanese FROM cards')
    rows = cursor.fetchall()
    
    init(autoreset=True)
    
    for row in rows:
        print(f"Word: {row[0]}, Vietnamese Translation: {Fore.BLUE}{row[1]}, Chinese: {Fore.BLUE}{row[2]}, Japanese: {Fore.BLUE}{row[3]}")
    
    connection.close()

@app.route('/')
def home():
    connection = sqlite3.connect('flashcards.db')
    cursor = connection.cursor()
    cursor.execute('SELECT vietnamese_translation FROM cards LIMIT 1')
    translation = cursor.fetchone()[0]  # Get the first translation
    connection.close()
    return render_template('index.html', translation=translation)

@app.route('/translate/<input_word>')
def translate(input_word):
    connection = sqlite3.connect('flashcards.db')
    cursor = connection.cursor()
    cursor.execute("SELECT english_word, vietnamese_translation, chinese, japanese FROM flashcards WHERE english_word=?", (input_word,))
    result = cursor.fetchone()

    connection.close()

    if result:
        return jsonify({
            'english_word': result[0],
            'vietnamese_translation': result[1],
            'chinese': result[2],
            'japanese': result[3]
        })
    else:
        return jsonify({'error': 'Word not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
