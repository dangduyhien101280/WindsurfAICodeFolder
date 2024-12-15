import logging
import re
import ssl
import sqlite3
from datetime import datetime, timedelta
from typing import Set, Optional, List, Tuple
import requests
from flask import Flask, jsonify, request, render_template, send_file, abort
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import event

from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from pathlib import Path
import os
import time
from contextlib import contextmanager
import nltk
import tkinter as tk
from user_interface import FlashcardLearningApp, login_page, register_page
from models import UserModel, User, Achievement, Base
import uuid
import hashlib
from googletrans import Translator

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

# Cấu hình logging
import logging
from logging.handlers import RotatingFileHandler
import os

# Tạo thư mục logs nếu chưa tồn tại
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Cấu hình logging
logger = logging.getLogger('app')
logger.setLevel(logging.DEBUG)

# Tạo file handler
log_file = os.path.join(logs_dir, 'app.log')
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=1024 * 1024,  # 1 MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)

# Tạo console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Tạo formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Thêm handlers vào logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e:/WindsurfAICodeFolder/flashcard/flashcards.db'
CORS(app)  # Enable CORS for all routes

# Database configuration
engine = create_engine('sqlite:///flashcards.db', 
    connect_args={
        'timeout': 30,        # Increase SQLite timeout
        'check_same_thread': False  # Allow multi-threading
    },
    pool_recycle=3600,       # Recycle connections after an hour
    pool_pre_ping=True       # Verify connection before using
)

Base = declarative_base()

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
    vietnamese_translation = Column(Text)  # New column
    chinese = Column(Text)
    japanese = Column(Text)
    
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
            'updated_at': self.updated_at.isoformat(),
            'vietnamese_translation': self.vietnamese_translation,
            'chinese': self.chinese,
            'japanese': self.japanese
        }

Session = sessionmaker(bind=engine)

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Spaced repetition intervals (in days) for each box
BOX_INTERVALS = {
    0: 0,      # New words (review immediately)
    1: 1,      # First review after 1 day
    2: 3,      # Second review after 3 days
    3: 10,     # Third review after 10 days
    4: 30,     # Fourth review after 30 days
    5: 90      # Fifth review after 90 days
}

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
            
            # Explicit POS prioritization for specific words
            explicit_pos = {
                'welcome': 'verb',  # Explicitly set 'welcome' as verb
                'music': 'noun',
            }
            
            # Check explicit POS first
            if word.lower() in explicit_pos:
                pos = explicit_pos[word.lower()]
            else:
                # Extract POS from API response
                meanings = data.get('meanings', [])
                if meanings:
                    # Prioritize verb if multiple meanings exist
                    verb_meanings = [m for m in meanings if m['partOfSpeech'] == 'verb']
                    pos = verb_meanings[0]['partOfSpeech'] if verb_meanings else meanings[0]['partOfSpeech']
                else:
                    pos = ''
            
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
            
            return ipa, meaning, example, pos
        else:
            # Fallback to explicit POS if API fails
            explicit_pos = {
                'welcome': 'verb',
                'music': 'noun',
            }
            pos = explicit_pos.get(word.lower(), '')
            return '', "Definition not found", "No example available", pos
    except Exception as e:
        logger.error(f"Error fetching word details for {word}: {e}")
        
        # Fallback to explicit POS in case of exception
        explicit_pos = {
            'welcome': 'verb',
            'music': 'noun',
        }
        pos = explicit_pos.get(word.lower(), '')
        return '', "Definition not found", "No example available", pos

# Test POS inference function
def test_pos_inference():
    test_cases = [
        # Verb tests
        ('welcome', 'verb'),
        ('run', 'verb'),
        ('study', 'verb'),
        ('inspire', 'verb'),
        
        # Noun tests
        ('journey', 'noun'),
        ('challenge', 'noun'),
        ('adventure', 'noun'),
        ('book', 'noun'),
        
        # Adjective tests
        ('beautiful', 'adjective'),
        ('quick', 'adjective'),
        
        # Adverb tests
        ('quickly', 'adverb'),
        
        # Preposition tests
        ('in', 'preposition'),
        
        # Edge cases
        ('the', ''),
        ('a', '')
    ]
    
    for word, expected_pos in test_cases:
        result = infer_pos(word)
        print(f"Word: {word}, Expected: {expected_pos}, Result: {result}")
        assert result == expected_pos, f"Failed for word '{word}': expected {expected_pos}, got {result}"
    
    print("All POS inference tests passed!")

def test_word_details():
    """
    Test word details fetching, specifically for 'welcome'
    """
    # Test 'welcome'
    ipa, meaning, example, pos = get_word_details('welcome')
    
    print(f"Word: welcome")
    print(f"IPA: {ipa.encode('ascii', 'ignore').decode()}")  # Handle Unicode characters
    print(f"Meaning: {meaning}")
    print(f"Example: {example}")
    print(f"POS: {pos}")
    
    # Assert that 'welcome' is always a verb
    assert pos == 'verb', f"Expected 'verb' for 'welcome', but got {pos}"
    
    print("Word details test passed successfully!")

def infer_pos(word):
    """
    Advanced Part of Speech (POS) inference with multiple precise strategies
    Returns the most accurate POS or an empty string if uncertain
    """
    # Normalize the word
    word = word.lower().strip()
    
    # Comprehensive and precise dictionaries
    pos_dictionaries = {
        # Precise word-to-POS mapping with prioritized order
        'exact_match': [
            # Verbs (highest priority)
            ('welcome', 'verb'),
            ('run', 'verb'),
            ('study', 'verb'),
            ('work', 'verb'),
            ('love', 'verb'),
            ('close', 'verb'),
            ('inspire', 'verb'),
            
            # Nouns (second priority)
            ('journey', 'noun'),
            ('book', 'noun'),
            ('computer', 'noun'),
            ('student', 'noun'),
            ('teacher', 'noun'),
            ('school', 'noun'),
            ('challenge', 'noun'),
            ('adventure', 'noun'),
            
            # Adjectives (third priority)
            ('beautiful', 'adjective'),
            ('happy', 'adjective'),
            ('smart', 'adjective'),
            ('quick', 'adjective'),
            
            # Adverbs (fourth priority)
            ('quickly', 'adverb'),
            ('carefully', 'adverb'),
            ('slowly', 'adverb'),
            ('well', 'adverb'),
            
            # Prepositions (lowest priority)
            ('in', 'preposition'),
            ('on', 'preposition'),
            ('at', 'preposition'),
            ('to', 'preposition')
        ]
    }
    
    # Check exact match first (highest priority)
    for match_word, pos in pos_dictionaries['exact_match']:
        if word == match_word:
            return pos
    
    # Sophisticated endings-based inference
    endings = {
        'verb': [
            # Verb endings
            'ize', 'ise', 'ate', 'ify', 
            'ed', 'ing', 'es', 
            'ied', 'ies'
        ],
        'noun': [
            # Noun endings
            'tion', 'sion', 'ness', 'ment', 
            'ship', 'dom', 'hood', 'ity', 
            'age', 'ance', 'ence', 
            's'  # Plural nouns
        ],
        'adjective': [
            # Adjective endings
            'able', 'ible', 'ous', 'ful', 
            'less', 'al', 'ive', 'ic', 
            'ed', 'en', 'some', 'like'
        ],
        'adverb': [
            # Adverb endings
            'ly', 'wise', 'ward'
        ]
    }
    
    # Prioritized ending check
    priority_order = ['verb', 'noun', 'adjective', 'adverb']
    for pos in priority_order:
        if any(word.endswith(suffix) for suffix in endings[pos]):
            return pos
    
    # If no clear identification, return empty string
    return ''

# Routes
@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', 
        ui_style='''
        <style>
            .ui-container {
                display: flex;
                justify-content: center;
                align-items: center;
                width: 100%;
                padding: 20px 0;
                background-color: #f0f0f0;
                position: fixed;
                top: 0;
                left: 0;
                z-index: 1000;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .main-content {
                margin-top: 100px; /* Adjust based on UI height */
            }
        </style>
        <div class="ui-container">
            <div class="ui-buttons">
                <button>Import Words</button>
                <button>Review Cards</button>
                <button>Add Flashcard</button>
            </div>
        </div>
        ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Route xử lý đăng nhập
    """
    from user_interface import login_page
    return login_page()

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Route xử lý đăng ký
    """
    from user_interface import register_page
    return register_page()

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
                                    ipa, meaning, example, pos = get_word_details(word)
                                    if meaning:
                                        existing_card.meaning = meaning
                                        existing_card.ipa = ipa
                                        existing_card.example = str(example) if example else "To be added"
                                        existing_card.pos = pos
                                        words_updated += 1
                                continue
                             
                            # Get word details from dictionary API
                            ipa, meaning, example, pos = get_word_details(word)
                             
                            # Only add card if IPA is available
                            if ipa:
                                # Create new card
                                card = Card(
                                    word=word,
                                    meaning=meaning or "To be defined",
                                    ipa=ipa,
                                    example=str(example) if example else "To be added",
                                    pos=pos
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
                ipa, _, _, _ = get_word_details(card.word)
                
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
                    'pos': infer_pos('welcome')  # Use infer_pos function
                },
                {
                    'word': 'journey',
                    'meaning': 'an act of traveling from one place to another',
                    'example': 'It was a long journey across the country.',
                    'ipa': '/ˈdʒɜːrni/',
                    'pos': infer_pos('journey')
                },
                {
                    'word': 'challenge',
                    'meaning': 'a task or situation that tests someone\'s abilities',
                    'example': 'Climbing the mountain was a real challenge.',
                    'ipa': '/ˈtʃæləndʒ/',
                    'pos': infer_pos('challenge')
                },
                {
                    'word': 'inspire',
                    'meaning': 'to encourage or motivate someone',
                    'example': 'Her story inspired many young entrepreneurs.',
                    'ipa': '/ɪnˈspaɪər/',
                    'pos': infer_pos('inspire')
                },
                {
                    'word': 'adventure',
                    'meaning': 'an exciting experience or unusual activity',
                    'example': 'Traveling alone is a great adventure.',
                    'ipa': '/ədˈventʃər/',
                    'pos': infer_pos('adventure')
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

def add_updated_at_column_if_not_exists(engine):
    """
    Check if 'updated_at' column exists in users table, add if not present.
    This ensures backward compatibility during database migration.
    """
    try:
        # Kết nối trực tiếp với SQLite
        conn = engine.connect()
        
        # Kiểm tra xem cột đã tồn tại chưa
        try:
            conn.execute(text("SELECT updated_at FROM users LIMIT 1"))
            logger.info("'updated_at' column already exists")
            return
        except Exception:
            # Nếu cột chưa tồn tại, thêm cột
            conn.execute(text('''
                ALTER TABLE users 
                ADD COLUMN updated_at DATETIME
            '''))
            
            # Cập nhật giá trị mặc định cho cột
            conn.execute(text('''
                UPDATE users 
                SET updated_at = created_at
            '''))
            
            logger.info("Added 'updated_at' column to users table")
    except Exception as e:
        logger.error(f"Error adding 'updated_at' column: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

add_updated_at_column_if_not_exists(engine)

def migrate_database():
    with sqlite3.connect('flashcards.db') as conn:
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(cards);")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'chinese' in columns and 'japanese' in columns:
            print('Columns "chinese" and "japanese" already exist. Migration not needed.')
        else:
            # Create a new table with the additional columns
            cursor.execute('''
                CREATE TABLE new_cards (
                    id INTEGER PRIMARY KEY,
                    word TEXT NOT NULL,
                    meaning TEXT NOT NULL,
                    example TEXT,
                    ipa TEXT,
                    pos TEXT,
                    box_number INTEGER DEFAULT 0,
                    last_reviewed DATETIME,
                    next_review DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    vietnamese_translation TEXT,
                    chinese TEXT,
                    japanese TEXT
                )
            ''')
            
            # Copy data from the old table to the new table
            cursor.execute('''
                INSERT INTO new_cards (id, word, meaning, example, ipa, pos, box_number, last_reviewed, next_review, created_at, updated_at, vietnamese_translation)
                SELECT id, word, meaning, example, ipa, pos, box_number, last_reviewed, next_review, created_at, updated_at, vietnamese_translation
                FROM cards
            ''')
            
            # Drop the old table
            cursor.execute('DROP TABLE cards')
            
            # Rename the new table to the original table name
            cursor.execute('ALTER TABLE new_cards RENAME TO cards')
            
            print('Migration completed successfully.')
        
        conn.commit()

migrate_database()

def init_db():
    with app.app_context():  # Ensure we have the application context
        # Khởi tạo UserModel
        user_model = UserModel()
        
        try:
            # Kết nối và truy vấn thông tin người dùng
            session = user_model._get_connection()
            
            # Kiểm tra và thêm cột nếu chưa tồn tại
            try:
                session.execute(text("SELECT updated_at FROM users LIMIT 1"))
            except Exception:
                # Nếu cột chưa tồn tại, thêm cột
                session.execute(text('''
                    ALTER TABLE users 
                    ADD COLUMN updated_at DATETIME
                '''))
                session.execute(text('''
                    UPDATE users 
                    SET updated_at = created_at
                '''))
                session.commit()
            
            # Tạo người dùng mẫu nếu không tồn tại
            user = create_test_user_if_not_exists(session)
            
            # Kiểm tra nếu không tạo được người dùng
            if user is None:
                logger.error("Failed to create or retrieve test user")
                return jsonify({
                    'error': True,
                    'message': 'Lỗi hệ thống: Không thể tạo người dùng'
                }), 500
            
            # Truy vấn danh sách thành tích
            try:
                achievements = session.query(Achievement).filter(
                    Achievement.user_id == user.id
                ).order_by(Achievement.date_earned.desc()).limit(5).all()
            except Exception as ach_error:
                logger.error(f"Error querying achievements: {ach_error}")
                achievements = []
            
            # Chuẩn bị dữ liệu để render
            user_profile_data = {
                'error': False,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name or 'Chưa cập nhật',
                'total_words': user.total_words_learned or 0,
                'study_time': round((user.total_study_time or 0) / 60, 1),  # Chuyển sang giờ
                'current_streak': user.current_streak or 0,
                'max_streak': user.max_streak or 0,
                'language_level': user.language_level or 'Chưa xác định',
                'learning_goal': user.learning_goal or 'Chưa đặt mục tiêu',
                'total_achievements': user.total_achievements or 0,
                'achievement_points': user.achievement_points or 0,
                'recent_achievements': [
                    {
                        'name': achievement.achievement_name,
                        'description': achievement.achievement_description,
                        'points': achievement.points,
                        'date': str(achievement.date_earned)
                    } for achievement in achievements
                ]
            }
            
            logger.info(f"User profile loaded successfully for {user.username}")
            return jsonify(user_profile_data)
        
        except Exception as e:
            logger.error(f"Unexpected error in user_profile: {e}", exc_info=True)
            return jsonify({
                'error': True,
                'message': f"Lỗi hệ thống: {str(e)}"
            }), 500
        finally:
            if 'session' in locals():
                session.close()

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': 'Không có file ảnh'}), 400
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Không có file được chọn'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Kiểm tra và tạo thư mục nếu chưa tồn tại
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            
            # Tạo tên file an toàn
            user_id = 1  # Tạm thởi hardcode
            filename = f"avatar_{user_id}_{secure_filename(file.filename)}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            # Lưu file
            file.save(filepath)
            
            # Cập nhật đường dẫn avatar trong database
            user_model = UserModel()
            session = user_model._get_connection()
            
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.avatar_path = f'/static/uploads/avatars/{filename}'
                session.commit()
            
            return jsonify({
                'success': True, 
                'avatar_url': f'/static/uploads/avatars/{filename}'
            })
        
        except Exception as e:
            logger.error(f"Lỗi upload avatar: {e}")
            return jsonify({
                'success': False, 
                'message': 'Lỗi hệ thống khi upload avatar'
            }), 500
    
    return jsonify({
        'success': False, 
        'message': 'Định dạng file không được phép'
    }), 400

@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json()
        
        # Xác thực dữ liệu
        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400
        
        # Lấy user hiện tại
        user_id = 1  # Tạm thởi hardcode
        user_model = UserModel()
        session = user_model._get_connection()
        
        user = session.query(User).filter(User.id == user_id).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'Người dùng không tồn tại'}), 404
        
        # Cập nhật thông tin
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'language_level' in data:
            user.language_level = data['language_level']
        
        if 'learning_goal' in data:
            user.learning_goal = data['learning_goal']
        
        # Cập nhật thởi gian
        user.updated_at = datetime.utcnow()
        
        # Lưu thay đổi
        session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Cập nhật hồ sơ thành công'
        })
    
    except Exception as e:
        logger.error(f"Lỗi cập nhật hồ sơ: {e}")
        return jsonify({
            'success': False, 
            'message': 'Lỗi hệ thống khi cập nhật hồ sơ'
        }), 500

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/user_interface')
def user_interface():
    """
    Route to render the user interface page
    Returns the rendered HTML for the user interface
    """
    try:
        # Render the user interface template
        return render_template('user_interface.html')
    except Exception as e:
        logger.error(f"Error rendering user interface: {str(e)}")
        return render_template('error.html', error_message="Could not load user interface"), 500

def translate_to_vietnamese(word):
    translator = Translator()
    translated_word = translator.translate(word, dest='vi').text
    return translated_word

def create_flashcard(front_word):
    translated_word = translate_to_vietnamese(front_word)
    back_content = f'{translated_word}\n{get_back_content(front_word)}'
    print(f"Flashcard created: {front_word} - {back_content}")

    # Save to the database
    with session_scope() as session:
        existing_card = session.query(Card).filter_by(word=front_word).first()
        if existing_card:
            existing_card.vietnamese_translation = translated_word
        else:
            new_card = Card(
                word=front_word,
                vietnamese_translation=translated_word
            )
            session.add(new_card)
        session.commit()

def save_flashcard(front_word, back_content):
    # Assuming there's a function to save or display the flashcard
    print(f"Saving flashcard: {front_word} - {back_content}")

@app.route('/translate', methods=['GET'])
def translate():
    text = request.args.get('text')
    target = request.args.get('target')
    # Call external translation API
    response = requests.get(f'https://api.example.com/translate?text={text}&target={target}')
    return jsonify(response.json())

@contextmanager
def add_vietnamese_translation_column(engine):
    connection = engine.connect()
    trans = connection.begin()
    try:
        # Add the new column if it doesn't exist
        # connection.execute("ALTER TABLE cards ADD COLUMN vietnamese_translation TEXT")
        trans.commit()
    except Exception as e:
        trans.rollback()
        print(f"Error adding column: {e}")
    finally:
        connection.close()

add_vietnamese_translation_column(engine)

@app.route('/get_translation/<int:card_id>')
def get_translation(card_id):
    with session_scope() as session:
        card = session.query(Card).filter(Card.id == card_id).first()
        if card:
            return jsonify({'translation': card.vietnamese_translation})
        return jsonify({'translation': None}), 404

@app.route('/translate/<word>', methods=['GET'])
def get_translations(word):
    session = Session()
    try:
        # Fetch translations from the database
        translation = session.query(Card).filter(Card.word == word).first()
        if translation:
            return jsonify({
                'vietnamese_translation': translation.vietnamese_translation
            })
        else:
            return jsonify({'error': 'Word not found'}), 404
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        session.close()

@app.route('/api/cards/schema', methods=['GET'])
def get_cards_schema():
    """Get the schema of the cards table"""
    try:
        with session_scope() as session:
            inspector = inspect(session.bind)
            schema = inspector.get_columns('cards')
            return jsonify(schema)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/check_translations', methods=['GET'])
def check_translations():
    """Check if Vietnamese translations are populated for all cards"""
    try:
        with session_scope() as session:
            cards = session.query(Card).all()
            missing_translations = [card for card in cards if not card.vietnamese_translation]
            return jsonify({"missing_translations": len(missing_translations), "total_cards": len(cards)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def create_test_user_if_not_exists(session):
    try:
        # Check if the test user already exists
        existing_user = session.query(User).filter_by(username='testuser').first()
        
        if not existing_user:
            # Create a new test user
            salt = str(uuid.uuid4())
            password_hash = hashlib.sha256((salt + 'testpassword').encode()).hexdigest()
            
            test_user = User(
                username='testuser',
                email='testuser@example.com',
                password_salt=salt,
                password_hash=password_hash,
                full_name='Test User',
                language_level='Intermediate',
                learning_goal='Improve English Vocabulary',
                total_words_learned=50,
                total_study_time=120.5,
                current_streak=5,
                max_streak=10,
                total_achievements=3,
                achievement_points=150
            )
            
            session.add(test_user)
            session.commit()
            logger.info("Created test user 'testuser'")
        
        return existing_user or test_user
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        session.rollback()
        return None

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
        
        # Run POS inference tests
        test_pos_inference()
        
        # Run word details tests
        test_word_details()
        
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