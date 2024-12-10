import logging
import re
import ssl
import sqlite3
from datetime import datetime, timedelta
from typing import Set, Optional, List, Tuple
import requests
from flask import Flask, jsonify, request, render_template, send_file, abort
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from pathlib import Path
import os
import time
from contextlib import contextmanager
import nltk

# Download necessary NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger', quiet=True)

# Optional ngrok import
try:
    from pyngrok import ngrok
    NGROK_AVAILABLE = True
except ImportError:
    NGROK_AVAILABLE = False
    ngrok = None

import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from flask_cors import CORS
except ImportError:
    print("Flask-CORS not found. Installing...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'flask-cors'])
    from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static', 
            static_url_path='/static')
CORS(app)  # Enable CORS for all routes

# Database configuration
Base = declarative_base()
engine = create_engine('sqlite:///flashcards.db', 
    connect_args={
        'timeout': 30,        # Increase SQLite timeout
        'check_same_thread': False  # Allow multi-threading
    },
    pool_recycle=3600,       # Recycle connections after an hour
    pool_pre_ping=True       # Verify connection before using
)
SessionLocal = sessionmaker(bind=engine)

# Configure audio directory
AUDIO_DIR = Path('static/audio').absolute()
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

class Card(Base):
    """Database model for flashcards with spaced repetition"""
    __tablename__ = 'cards'
    
    id = Column(Integer, primary_key=True)
    word = Column(String(100), nullable=False, index=True, unique=True)
    meaning = Column(Text, nullable=False)
    example = Column(Text)
    ipa = Column(String(100))
    pos = Column(String(50))  # New column for Part of Speech
    box_number = Column(Integer, default=0)  # New column
    last_reviewed = Column(DateTime)         # New column
    next_review = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert card to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'word': self.word,
            'meaning': self.meaning,
            'example': self.example,
            'ipa': self.ipa,
            'pos': self.pos,  # Include POS in dictionary
            'box_number': self.box_number,
            'last_reviewed': self.last_reviewed.isoformat() if self.last_reviewed else None,
            'next_review': self.next_review.isoformat() if self.next_review else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# Spaced repetition intervals (in days) for each box
BOX_INTERVALS = {
    0: 0,      # New words (review immediately)
    1: 1,      # First review after 1 day
    2: 3,      # Second review after 3 days
    3: 10,     # Third review after 10 days
    4: 30,     # Fourth review after 30 days
    5: 90      # Fifth review after 90 days
}

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        if isinstance(e, sqlite3.OperationalError) and "database is locked" in str(e):
            logger.warning("Database lock detected, rolling back transaction")
            time.sleep(0.1)  # Small delay before retrying
        raise
    finally:
        session.close()

def retry_operation(func):
    """Decorator to retry operations with exponential backoff"""
    def wrapper(*args, **kwargs):
        max_attempts = 3
        attempt = 1
        while attempt <= max_attempts:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_attempts:
                    logger.error(f"Final attempt failed: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt} failed, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff
                attempt += 1
    wrapper.__name__ = f"{func.__name__}_retry"  # Give each wrapped function a unique name
    return wrapper

def get_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([^"&?/\s]{11})',
        r'(?:embed/)([^"&?/\s]{11})',
        r'(?:watch\?v=)([^"&?/\s]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_words_from_transcript(transcript):
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

def get_word_definition(word):
    # Simple definition generation
    definitions = {
        'welcome': 'to greet someone in a polite or friendly way',
        'journey': 'an act of traveling from one place to another',
        'challenge': 'a task or situation that tests someone\'s abilities',
        'inspire': 'to encourage or motivate someone',
        'adventure': 'an exciting experience or unusual activity'
    }
    
    return definitions.get(word, f'A word commonly used in context.')

def get_word_details(word):
    """
    Fetch word details from a dictionary API with improved robustness
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
            
            # Extract IPA with more robust checking
            ipa = ''
            if data.get('phonetics'):
                # Try to find a non-empty IPA
                for phonetic in data['phonetics']:
                    if phonetic.get('text'):
                        ipa = phonetic['text']
                        break
            
            return ipa, meaning, example
        else:
            return '', "Definition not found", "No example available"
    except Exception as e:
        logger.error(f"Error fetching word details for {word}: {e}")
        return '', "Definition not found", "No example available"

def infer_pos(word):
    """
    Infer part of speech with high precision
    Returns the most accurate POS or an empty string if uncertain
    """
    # Normalize the word
    word = word.lower().strip()
    
    # Comprehensive dictionary of known words with their POS
    pos_dictionary = {
        # Pronouns
        'i': 'pronoun', 'me': 'pronoun', 'my': 'pronoun',
        'you': 'pronoun', 'your': 'pronoun',
        'he': 'pronoun', 'him': 'pronoun', 'his': 'pronoun',
        'she': 'pronoun', 'her': 'pronoun', 'hers': 'pronoun',
        'it': 'pronoun', 'its': 'pronoun',
        'we': 'pronoun', 'us': 'pronoun', 'our': 'pronoun',
        'they': 'pronoun', 'them': 'pronoun', 'their': 'pronoun',
        
        # Articles
        'the': '', 'a': '', 'an': '',
        
        # Conjunctions
        'and': '', 'but': '', 'or': '', 'nor': '', 'for': '', 
        'yet': '', 'so': '',
        
        # Prepositions
        'in': 'preposition', 'on': 'preposition', 'at': 'preposition', 
        'to': 'preposition', 'for': 'preposition', 'with': 'preposition', 
        'by': 'preposition', 'from': 'preposition', 'of': 'preposition', 
        'about': 'preposition', 'under': 'preposition', 'over': 'preposition',
        
        # Common adverbs
        'here': 'adverb', 'there': 'adverb', 'now': 'adverb', 
        'then': 'adverb', 'always': 'adverb', 'never': 'adverb', 
        'sometimes': 'adverb', 'often': 'adverb', 'rarely': 'adverb',
        'very': 'adverb', 'too': 'adverb', 'almost': 'adverb',
        
        # Demonstratives
        'this': 'pronoun', 'that': 'pronoun', 
        'these': 'pronoun', 'those': 'pronoun'
    }
    
    # Check dictionary first
    if word in pos_dictionary:
        return pos_dictionary[word]
    
    # Endings-based inference (more precise)
    endings = {
        'noun': ['tion', 'sion', 'ness', 'ment', 'ship', 
                 'dom', 'hood', 'ity', 'age', 'ance', 'ence'],
        'verb': ['ize', 'ise', 'ate', 'en', 'ify', 'ed', 'ing'],
        'adjective': ['able', 'ible', 'ous', 'ful', 'less', 
                      'al', 'ive', 'ic', 'ed', 'en'],
        'adverb': ['ly']
    }
    
    # Check endings
    for pos, suffixes in endings.items():
        if any(word.endswith(suffix) for suffix in suffixes):
            return pos
    
    # Special cases for some irregular words
    if word.endswith('s') and len(word) > 2:
        # Potential noun or verb (3rd person singular)
        return 'noun'
    
    # If no clear identification, return empty string
    return ''

# Routes
@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/cards')
def get_cards():
    """Get all flashcards"""
    try:
        with session_scope() as session:
            cards = session.query(Card).all()
            return jsonify([card.to_dict() for card in cards])
    except Exception as e:
        logger.error(f"Error in get_cards: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/speak/<word>')
def speak_word(word):
    try:
        # Validate and convert rate parameter
        rate = float(request.args.get('rate', 1.0))
        rate = max(0.5, min(rate, 2.0))  # Clamp rate between 0.5 and 2.0
        
        # Create audio directory if not exists
        audio_dir = os.path.join(app.static_folder, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate unique filename based on word and rate
        safe_word = ''.join(c for c in word.lower() if c.isalnum())
        filename = f"{safe_word}_{rate}.mp3"
        filepath = os.path.join(audio_dir, filename)
        
        # Check if audio file already exists
        if not os.path.exists(filepath):
            # Generate base audio file with gTTS
            tts = gTTS(text=word, lang='en', slow=(rate < 1.0))
            tts.save(filepath)
        
        return send_file(filepath, mimetype='audio/mpeg')
    
    except Exception as e:
        logger.error(f"Error generating speech for word '{word}': {str(e)}")
        return jsonify({"error": "Failed to generate speech"}), 500

@app.route('/api/cards/<int:card_id>/learned', methods=['POST'])
@retry_operation
def mark_learned(card_id: int):
    """Mark a card as learned"""
    try:
        with session_scope() as session:
            card = session.query(Card).get(card_id)
            if not card:
                abort(404)
            
            card.learned = True
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in mark_learned: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/<int:card_id>/review', methods=['POST'])
def review_card(card_id: int):
    """Review a card and update its box number based on the result"""
    try:
        data = request.get_json()
        correct = data.get('correct', False)
        
        with session_scope() as session:
            card = session.query(Card).get(card_id)
            if not card:
                return jsonify({'error': 'Card not found'}), 404
                
            now = datetime.utcnow()
            card.last_reviewed = now
            
            if correct:
                # Move to next box if answered correctly
                if card.box_number < 5:
                    card.box_number += 1
            else:
                # Move back to box 1 if answered incorrectly
                card.box_number = 1
                
            # Calculate next review date
            days = BOX_INTERVALS[card.box_number]
            card.next_review = now + timedelta(days=days)
            
            session.commit()
            return jsonify(card.to_dict())
    except Exception as e:
        logger.error(f"Error in review_card: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/due')
def get_due_cards():
    """Get all cards due for review"""
    try:
        now = datetime.utcnow()
        with session_scope() as session:
            cards = session.query(Card).filter(
                (Card.next_review <= now) | (Card.next_review == None)
            ).all()
            return jsonify([card.to_dict() for card in cards])
    except Exception as e:
        logger.error(f"Error in get_due_cards: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/stats')
def get_box_stats():
    """Get statistics about cards in each box"""
    try:
        with session_scope() as session:
            stats = {}
            total_cards = session.query(Card).count()
            for box in range(6):
                count = session.query(Card).filter(Card.box_number == box).count()
                stats[f'box_{box}'] = {
                    'count': count,
                    'percentage': round((count / total_cards * 100) if total_cards > 0 else 0, 1)
                }
            stats['total'] = total_cards
            return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in get_box_stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-youtube', methods=['POST'])
@retry_operation
def import_youtube():
    """Import words from YouTube video subtitles"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
            
        url = data['url']
        video_id = get_youtube_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Try getting transcript in multiple languages
        languages_to_try = ['en', 'vi', 'auto']
        transcript = None
        
        for lang in languages_to_try:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                break
            except Exception as e:
                logger.warning(f"Couldn't get transcript in {lang}: {e}")
        
        if not transcript:
            return jsonify({'error': 'No transcript available in any language'}), 400
        
        # Extract words from transcript
        words: Set[str] = set()
        words = extract_words_from_transcript(transcript)
        
        words_added = 0
        words_updated = 0
        batch_size = 10  # Smaller batch size for better lock handling
        
        # Process words in smaller transactions
        for i in range(0, len(words), batch_size):
            word_batch = words[i:i + batch_size]
            with session_scope() as session:
                # Disable autoflush to prevent premature constraint checks
                with session.no_autoflush:
                    for word in word_batch:
                        try:
                            # Check if word exists
                            existing_card = session.query(Card).filter_by(word=word).first()
                             
                            if existing_card:
                                # Update existing card if it has no meaning
                                if existing_card.meaning == "To be defined":
                                    ipa, meaning, example = get_word_details(word)
                                    if meaning:
                                        existing_card.meaning = meaning
                                        existing_card.ipa = ipa
                                        existing_card.example = str(example) if example else "To be added"
                                        words_updated += 1
                                continue
                             
                            # Get word details from dictionary API
                            ipa, meaning, example = get_word_details(word)
                             
                            # Only add card if IPA is available
                            if ipa:
                                # Create new card
                                card = Card(
                                    word=word,
                                    meaning=meaning or "To be defined",
                                    ipa=ipa,
                                    example=str(example) if example else "To be added",
                                    pos=infer_pos(word)
                                )
                                session.merge(card)  # Use merge instead of add
                                words_added += 1
                             
                        except Exception as e:
                            logger.error(f"Error processing word '{word}': {str(e)}")
                            continue
                
                # Commit each batch
                try:
                    session.flush()
                except Exception as e:
                    logger.error(f"Error flushing batch: {str(e)}")
                    session.rollback()
                    continue
                
        return jsonify({
            'success': True, 
            'words_added': words_added
        })
        
    except Exception as e:
        logger.error(f"Error importing from YouTube: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/youtube/import', methods=['POST'])
def import_youtube_words():
    try:
        data = request.get_json()
        youtube_url = data.get('url', '')
        
        # Extract video ID from URL
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
        if not video_id_match:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        video_id = video_id_match.group(1)
        
        # Get transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        # Extract unique words
        words = extract_words_from_transcript(transcript)
        
        # Import words to database
        imported_count = 0
        with session_scope() as session:
            for word in words[:20]:  # Limit to 20 words
                # Check if word already exists
                existing_card = session.query(Card).filter_by(word=word).first()
                if not existing_card:
                    new_card = Card(
                        word=word,
                        meaning=get_word_definition(word),
                        example=f'From YouTube video: {youtube_url}',
                        box_number=0,
                        next_review=datetime.utcnow(),
                        pos=infer_pos(word)
                    )
                    session.add(new_card)
                    imported_count += 1
            
            session.commit()
        
        return jsonify({
            'imported': imported_count,
            'total_words_found': len(words)
        })
    
    except Exception as e:
        logger.error(f"YouTube import error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/cleanup', methods=['POST'])
def cleanup_incomplete_cards():
    """Remove cards without IPA transcription"""
    try:
        with session_scope() as session:
            # Find and delete cards without IPA
            incomplete_cards = session.query(Card).filter(
                (Card.ipa == '') | (Card.ipa == None)
            ).all()
            
            # Count the number of cards to be deleted
            cards_to_delete_count = len(incomplete_cards)
            
            # Delete the incomplete cards
            for card in incomplete_cards:
                session.delete(card)
            
            # Commit the changes
            session.commit()
            
            return jsonify({
                'success': True, 
                'cards_removed': cards_to_delete_count
            })
    except Exception as e:
        logger.error(f"Error cleaning up incomplete cards: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/cards/update_ipa', methods=['POST'])
def update_card_ipa():
    """Update IPA for existing cards"""
    try:
        with session_scope() as session:
            # Find cards without IPA
            cards_without_ipa = session.query(Card).filter(
                (Card.ipa == '') | (Card.ipa == None)
            ).all()
            
            updated_count = 0
            for card in cards_without_ipa:
                # Try to fetch IPA for the word
                ipa, _, _ = get_word_details(card.word)
                
                if ipa:
                    card.ipa = ipa
                    updated_count += 1
            
            session.commit()
            
            return jsonify({
                'success': True, 
                'cards_updated': updated_count
            })
    except Exception as e:
        logger.error(f"Error updating card IPAs: {str(e)}")
        return jsonify({'error': str(e)}), 400

def remove_incomplete_cards():
    """
    Remove cards without IPA transcription directly in the database
    
    Returns:
        int: Number of cards removed
    """
    try:
        with session_scope() as session:
            # Find and delete cards without IPA
            incomplete_cards = session.query(Card).filter(
                (Card.ipa == '') | (Card.ipa == None)
            ).all()
            
            # Count and log the number of cards to be deleted
            cards_to_delete_count = len(incomplete_cards)
            logger.info(f"Removing {cards_to_delete_count} cards without IPA")
            
            # Delete the incomplete cards
            for card in incomplete_cards:
                logger.info(f"Removing card: {card.word}")
                session.delete(card)
            
            return cards_to_delete_count
    except Exception as e:
        logger.error(f"Error removing incomplete cards: {str(e)}")
        return 0

# Optional: Add a CLI method to trigger card cleanup
def cleanup_cards_cli():
    """
    Command-line interface method to remove incomplete cards
    Can be called directly from the script
    """
    try:
        removed_count = remove_incomplete_cards()
        print(f"Removed {removed_count} cards without IPA")
        return removed_count
    except Exception as e:
        logger.error(f"Error in cleanup_cards_cli: {str(e)}")
        return 0

def reset_database():
    """
    Completely reset the database by:
    1. Dropping all existing tables
    2. Recreating tables
    3. Reinitializing with sample data
    """
    try:
        # Drop all existing tables
        Base.metadata.drop_all(engine)
        logger.info("Existing database tables dropped")
        
        # Recreate all tables
        Base.metadata.create_all(engine)
        logger.info("Database tables recreated")
        
        # Initialize with sample words
        with session_scope() as session:
            sample_words = [
                {
                    'word': 'welcome',
                    'meaning': 'to greet someone in a polite or friendly way',
                    'example': 'They welcomed us with open arms.',
                    'ipa': '/ˈwelkəm/',
                    'pos': 'verb'
                },
                {
                    'word': 'journey',
                    'meaning': 'an act of traveling from one place to another',
                    'example': 'It was a long journey across the country.',
                    'ipa': '/ˈdʒɜːrni/',
                    'pos': 'noun'
                },
                {
                    'word': 'challenge',
                    'meaning': 'a task or situation that tests someone\'s abilities',
                    'example': 'Climbing the mountain was a real challenge.',
                    'ipa': '/ˈtʃæləndʒ/',
                    'pos': 'noun'
                },
                {
                    'word': 'inspire',
                    'meaning': 'to encourage or motivate someone',
                    'example': 'Her story inspired many young entrepreneurs.',
                    'ipa': '/ɪnˈspaɪər/',
                    'pos': 'verb'
                },
                {
                    'word': 'adventure',
                    'meaning': 'an exciting experience or unusual activity',
                    'example': 'Traveling alone is a great adventure.',
                    'ipa': '/ədˈventʃər/',
                    'pos': 'noun'
                }
            ]
            
            for word_data in sample_words:
                card = Card(
                    word=word_data['word'],
                    meaning=word_data['meaning'],
                    example=word_data['example'],
                    ipa=word_data['ipa'],
                    pos=word_data['pos'],
                    box_number=0,
                    next_review=datetime.utcnow()
                )
                session.add(card)
            
            session.commit()
            logger.info("Database reinitialized with sample words")
        
        return True
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        return False

def add_pos_column_if_not_exists(engine):
    """
    Check if 'pos' column exists in cards table, add if not present.
    This ensures backward compatibility during database migration.
    """
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('cards')]
        
        if 'pos' not in columns:
            print("Adding 'pos' column to cards table...")
            with engine.begin() as connection:
                connection.execute(f"ALTER TABLE cards ADD COLUMN pos VARCHAR(50)")
            print("'pos' column added successfully!")
    except Exception as e:
        print(f"Error checking/adding 'pos' column: {e}")

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Ensure pos column exists
    add_pos_column_if_not_exists(engine)
    
    # Rest of the init_db function remains the same
    session = SessionLocal()
    try:
        # Check if database is empty
        card_count = session.query(Card).count()
        if card_count == 0:
            # Sample words with initial data
            sample_words = [
                {"word": "hello", "translation": "안녕하세요", "language": "korean"},
                {"word": "goodbye", "translation": "안녕히 가세요", "language": "korean"},
                {"word": "thank", "translation": "감사합니다", "language": "korean"}
            ]
            
            for word_data in sample_words:
                card = Card(
                    word=word_data['word'], 
                    translation=word_data['translation'], 
                    language=word_data['language'],
                    pos=infer_pos(word_data['word'])  # Add POS inference here
                )
                session.add(card)
            
            session.commit()
            print("Initialized database with sample words")
    except Exception as e:
        session.rollback()
        print(f"Error initializing database: {e}")
    finally:
        session.close()

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    import sys
    import traceback
    
    try:
        # Check if cleanup flag is passed
        if '--cleanup-cards' in sys.argv:
            cleanup_cards_cli()
        
        # Check if reset flag is passed
        if '--reset-db' in sys.argv:
            reset_database()
            print("Database has been reset and reinitialized.")
            sys.exit(0)
        
        # Initialize database
        init_db()
        
        # Ensure database is populated
        with session_scope() as session:
            card_count = session.query(Card).count()
            print(f"Total cards in database: {card_count}")
            if card_count == 0:
                print("WARNING: No cards in database. Consider adding sample data.")
        
        # Optionally start ngrok tunnel
        public_url = None
        if NGROK_AVAILABLE:
            try:
                public_url = ngrok.connect(5000)
                print(f"Public URL: {public_url}")
            except Exception as ngrok_error:
                print(f"Failed to start ngrok tunnel: {ngrok_error}")
        
        # Run the app directly
        print("Starting Flask application...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    
    except Exception as e:
        print("An error occurred while starting the application:")
        print(traceback.format_exc())
        sys.exit(1)