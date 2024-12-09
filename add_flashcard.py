#!python
import sqlite3
import datetime
import sys
import argparse

def connect_to_database():
    """Establish a connection to the SQLite database."""
    return sqlite3.connect('flashcards.db')

def add_flashcard(word, meaning, meaning_vn=None, example=None, example_vn=None, ipa=None):
    """
    Add or update a flashcard in the database.
    
    Args:
        word (str): The word to add
        meaning (str): The word's meaning
        meaning_vn (str, optional): Vietnamese meaning
        example (str, optional): Example sentence
        example_vn (str, optional): Vietnamese example
        ipa (str, optional): IPA pronunciation
    """
    conn = connect_to_database()
    cursor = conn.cursor()
    
    try:
        # Get current timestamp
        now = datetime.datetime.now()
        
        # Check if word already exists
        cursor.execute('SELECT id FROM cards WHERE word = ?', (word,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE cards 
                SET meaning = ?, meaning_vn = ?, example = ?, example_vn = ?, ipa = ?, 
                    updated_at = ?, box_number = 1
                WHERE word = ?
            ''', (
                meaning, meaning_vn, example, example_vn, ipa, 
                now, word
            ))
            print(f"Flashcard for '{word}' updated successfully!")
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO cards 
                (word, meaning, meaning_vn, example, example_vn, ipa, box_number, 
                last_reviewed, next_review, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                word, meaning, meaning_vn, example, example_vn, ipa, 
                1,  # Start in box 1 for spaced repetition
                None, None,  # No initial review
                now, now  # creation and update timestamps
            ))
            print(f"Flashcard for '{word}' added successfully!")
        
        conn.commit()
        return True
    
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Add or update flashcards in the database.')
    parser.add_argument('word', help='The word to add')
    parser.add_argument('meaning', help='The meaning of the word')
    parser.add_argument('--meaning_vn', help='Vietnamese meaning (optional)', default=None)
    parser.add_argument('--example', help='Example sentence (optional)', default=None)
    parser.add_argument('--example_vn', help='Vietnamese example (optional)', default=None)
    parser.add_argument('--ipa', help='IPA pronunciation (optional)', default=None)
    
    args = parser.parse_args()
    
    add_flashcard(
        args.word, 
        args.meaning, 
        args.meaning_vn, 
        args.example, 
        args.example_vn, 
        args.ipa
    )

if __name__ == '__main__':
    main()
