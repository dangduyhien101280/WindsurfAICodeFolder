import sys
import sqlite3
import requests
from youtube_transcript_api import YouTubeTranscriptApi
import re

def get_word_details(word):
    """
    Fetch word details from a dictionary API
    """
    try:
        # Use Free Dictionary API
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        if response.status_code == 200:
            data = response.json()[0]
            
            # Extract meaning
            meaning = data['meanings'][0]['definitions'][0]['definition'] if data['meanings'] else "No definition found"
            
            # Extract example (if available)
            example = data['meanings'][0]['definitions'][0].get('example', "No example available")
            
            return meaning, example
        else:
            return "Definition not found", "No example available"
    except Exception as e:
        print(f"Error fetching word details for {word}: {e}")
        return "Definition not found", "No example available"

def extract_unique_words(transcript):
    """
    Extract unique words from YouTube transcript
    """
    # Combine all transcript text
    full_text = ' '.join([entry['text'] for entry in transcript])
    
    # Use regex to extract words
    words = re.findall(r'\b[a-z]{3,}\b', full_text.lower())
    
    # Remove duplicates while preserving order
    unique_words = []
    seen = set()
    for word in words:
        if word not in seen:
            unique_words.append(word)
            seen.add(word)
    
    return unique_words

def import_youtube_words(video_url):
    """
    Import words from YouTube video transcript to SQLite database
    """
    conn = None
    
    try:
        # Extract video ID
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', video_url)
        if not video_id_match:
            print("Invalid YouTube URL")
            return
        
        video_id = video_id_match.group(1)
        
        # Get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Extract unique words
        words = extract_unique_words(transcript)
        
        # Connect to SQLite database
        conn = sqlite3.connect('e:/WindsurfAICodeFolder/flashcards.db')
        cursor = conn.cursor()
        
        # Track import statistics
        words_added = 0
        words_updated = 0
        
        for word in words[:50]:  # Limit to first 50 words
            try:
                # Check if word already exists
                cursor.execute('SELECT id FROM cards WHERE word = ?', (word,))
                existing = cursor.fetchone()
                
                # Get word details
                meaning, example = get_word_details(word)
                
                if existing:
                    # Update existing word
                    cursor.execute('''
                        UPDATE cards 
                        SET meaning = ?, example = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE word = ?
                    ''', (meaning, example, word))
                    words_updated += 1
                else:
                    # Insert new word
                    cursor.execute('''
                        INSERT INTO cards 
                        (word, meaning, example, box_number, created_at, updated_at) 
                        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (word, meaning, example))
                    words_added += 1
            
            except Exception as e:
                print(f"Error processing word {word}: {e}")
        
        # Commit changes
        conn.commit()
        
        print(f"Import complete. Words added: {words_added}, Words updated: {words_updated}")
    
    except Exception as e:
        print(f"Error importing YouTube words: {e}")
    
    finally:
        if conn:
            conn.close()

def main():
    if len(sys.argv) < 2:
        print("Please provide a YouTube video URL")
        return
    
    video_url = sys.argv[1]
    import_youtube_words(video_url)

if __name__ == '__main__':
    main()
