import nltk
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

from flask import Flask, render_template, jsonify, request, send_file, abort
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session
from contextlib import contextmanager
from datetime import datetime, timedelta
from gtts import gTTS
from youtube_transcript_api import YouTubeTranscriptApi
import re
import os
import logging
import sqlite3
import random
from typing import Optional, Set, List, Tuple
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

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
    # Combine all transcript text
    full_text = ' '.join([entry['text'] for entry in transcript])
    
    # Tokenize and tag words
    words = nltk.word_tokenize(full_text)
    tagged_words = nltk.pos_tag(words)
    
    # Filter unique nouns and verbs
    unique_words = set()
    for word, tag in tagged_words:
        # Clean word: lowercase, remove punctuation
        clean_word = re.sub(r'[^\w\s]', '', word.lower())
        
        # Filter conditions
        if (len(clean_word) > 2 and  # More than 2 characters
            clean_word not in unique_words and  # Unique
            tag in ['NN', 'NNS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ']):  # Nouns and Verbs
            unique_words.add(clean_word)
    
    return list(unique_words)

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

def get_word_details(word: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Get word details from Free Dictionary API"""
    import requests
    
    api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()[0]
            
            # Get IPA
            ipa = None
            if 'phonetic' in data:
                ipa = data['phonetic']
            elif 'phonetics' in data and data['phonetics']:
                for phonetic in data['phonetics']:
                    if 'text' in phonetic:
                        ipa = phonetic['text']
                        break
            
            # Get meaning and example
            meaning = None
            example = None
            if 'meanings' in data and data['meanings']:
                first_meaning = data['meanings'][0]
                if 'definitions' in first_meaning and first_meaning['definitions']:
                    first_def = first_meaning['definitions'][0]
                    meaning = first_def.get('definition')
                    example = first_def.get('example')
            
            return ipa, meaning, example
            
    except Exception as e:
        logger.error(f"Error fetching word details for '{word}': {str(e)}")
    
    return None, None, None

# Routes
@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/cards')
def get_cards():
    """Get all flashcards"""
    with session_scope() as session:
        cards = session.query(Card).all()
        return jsonify([card.to_dict() for card in cards])

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
    with session_scope() as session:
        card = session.query(Card).get(card_id)
        if not card:
            abort(404)
        
        card.learned = True
        return jsonify({'success': True})

@app.route('/api/cards/<int:card_id>/review', methods=['POST'])
def review_card(card_id: int):
    """Review a card and update its box number based on the result"""
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

@app.route('/api/cards/due')
def get_due_cards():
    """Get all cards due for review"""
    now = datetime.utcnow()
    with session_scope() as session:
        cards = session.query(Card).filter(
            (Card.next_review <= now) | (Card.next_review == None)
        ).all()
        return jsonify([card.to_dict() for card in cards])

@app.route('/api/cards/stats')
def get_box_stats():
    """Get statistics about cards in each box"""
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
        
        # Get video transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        words: Set[str] = set()
        
        # Extract words from transcript
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
                            
                            # Create new card
                            card = Card(
                                word=word,
                                meaning=meaning or "To be defined",
                                ipa=ipa,
                                example=str(example) if example else "To be added"
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
            'words_added': words_added,
            'words_updated': words_updated
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
                        next_review=datetime.utcnow()
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

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

def init_db():
    """Initialize database with sample words"""
    Base.metadata.create_all(engine)
    
    # Check if database is empty
    with session_scope() as session:
        if session.query(Card).count() == 0:
            # Sample vocabulary words
            sample_words = [
                {
                    'word': 'welcome',
                    'meaning': 'to greet someone in a polite or friendly way',
                    'example': 'They welcomed us with open arms.',
                    'ipa': '/ˈwelkəm/'
                },
                {
                    'word': 'journey',
                    'meaning': 'an act of traveling from one place to another',
                    'example': 'It was a long journey across the country.',
                    'ipa': '/ˈdʒɜːrni/'
                },
                {
                    'word': 'challenge',
                    'meaning': 'a task or situation that tests someone\'s abilities',
                    'example': 'Climbing the mountain was a real challenge.',
                    'ipa': '/ˈtʃæləndʒ/'
                },
                {
                    'word': 'inspire',
                    'meaning': 'to encourage or motivate someone',
                    'example': 'Her story inspired many young entrepreneurs.',
                    'ipa': '/ɪnˈspaɪər/'
                },
                {
                    'word': 'adventure',
                    'meaning': 'an exciting experience or unusual activity',
                    'example': 'Traveling alone is a great adventure.',
                    'ipa': '/ədˈventʃər/'
                }
            ]
            
            for word_data in sample_words:
                card = Card(
                    word=word_data['word'],
                    meaning=word_data['meaning'],
                    example=word_data['example'],
                    ipa=word_data['ipa'],
                    box_number=0,
                    next_review=datetime.utcnow()
                )
                session.add(card)
            
            session.commit()
            logger.info("Database initialized with sample words")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)