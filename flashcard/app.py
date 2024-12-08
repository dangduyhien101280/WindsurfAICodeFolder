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
import json
import logging
import sqlite3
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
    """Database model for flashcards"""
    __tablename__ = 'cards'
    
    id = Column(Integer, primary_key=True)
    word = Column(String(100), nullable=False, index=True, unique=True)
    meaning = Column(Text, nullable=False)
    example = Column(Text)
    ipa = Column(String(100))
    learned = Column(Boolean, default=False)
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
            'learned': self.learned,
            'next_review': self.next_review.isoformat() if self.next_review else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
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
def speak_word(word: str):
    """Generate and serve audio for word pronunciation"""
    try:
        # Create filename from word and ensure directory exists
        filename = f"{word.lower()}.mp3"
        filepath = AUDIO_DIR / filename
        
        # Ensure audio directory exists
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate audio if it doesn't exist
        if not filepath.exists():
            try:
                tts = gTTS(text=word, lang='en')
                tts.save(str(filepath))
            except Exception as e:
                logger.error(f"Error generating audio file for '{word}': {str(e)}")
                return jsonify({'error': f"Failed to generate audio for '{word}'"}), 500
        
        if not filepath.exists():
            logger.error(f"Audio file not found after generation attempt: {filepath}")
            return jsonify({'error': 'Audio file generation failed'}), 500
            
        try:
            return send_file(
                str(filepath),
                mimetype='audio/mpeg',
                as_attachment=False
            )
        except Exception as e:
            logger.error(f"Error serving audio file '{filepath}': {str(e)}")
            return jsonify({'error': 'Failed to serve audio file'}), 500
            
    except Exception as e:
        logger.error(f"Error in speak_word for '{word}': {str(e)}")
        return jsonify({'error': str(e)}), 400

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
@retry_operation
def schedule_review(card_id: int):
    """Schedule a card for review"""
    with session_scope() as session:
        card = session.query(Card).get(card_id)
        if not card:
            abort(404)
        
        card.next_review = datetime.utcnow() + timedelta(days=1)
        return jsonify({'success': True})

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
        for entry in transcript:
            text = entry['text'].lower()
            # Extract words with length > 3 and only letters
            words.update(
                word for word in re.findall(r'\b[a-z]+\b', text)
                if len(word) > 3
            )
        
        words_added = 0
        words_updated = 0
        batch_size = 10  # Smaller batch size for better lock handling
        
        # Process words in smaller transactions
        for i in range(0, len(words), batch_size):
            word_batch = list(words)[i:i + batch_size]
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

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500

# Create database tables
Base.metadata.create_all(engine)

if __name__ == '__main__':
    app.run(debug=True)