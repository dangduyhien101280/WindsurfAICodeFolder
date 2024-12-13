import sqlite3
import sys
import io

# Set the encoding for stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_cards():
    connection = sqlite3.connect('flashcards.db')
    cursor = connection.cursor()
    
    cursor.execute('SELECT word, vietnamese_translation FROM cards')
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"Word: {row[0]}, Vietnamese Translation: {row[1]}")
    
    connection.close()

if __name__ == '__main__':
    check_cards()
