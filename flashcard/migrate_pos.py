import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import Column, String, inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from app import SessionLocal, Card, datetime, Base, engine

def add_pos_column():
    """Add pos column to existing database"""
    try:
        inspector = inspect(engine)
        
        # Check if column exists
        columns = [col['name'] for col in inspector.get_columns('cards')]
        
        if 'pos' not in columns:
            print("Adding 'pos' column to cards table...")
            
            # Use text() to create an executable SQL statement
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE cards ADD COLUMN pos VARCHAR(50)"))
            
            print("'pos' column added successfully!")
    except SQLAlchemyError as e:
        print(f"Error adding column: {e}")
        # If column already exists, ignore the error
        if "duplicate column" not in str(e).lower():
            raise

def infer_pos(word):
    """
    Advanced POS inference based on word characteristics
    
    More sophisticated rules for determining part of speech
    """
    word = word.lower()
    
    # Predefined lists for more accurate classification
    verb_endings = [
        # Verb endings
        'ize', 'ise', 'ate', 'en', 'ify', 'ed', 'ing', 
        # Past tense verb endings
        'ed', 'ied', 'en', 'ought', 'ent', 'ew'
    ]
    
    noun_endings = [
        # Noun endings
        'tion', 'sion', 'ness', 'ment', 'ship', 'dom', 'hood', 
        'er', 'or', 'ist', 'ian', 'man', 'men', 
        'ity', 'ty', 'age', 'ence', 'ance'
    ]
    
    adj_endings = [
        # Adjective endings
        'able', 'ible', 'ous', 'ful', 'less', 'al', 'ive', 
        'ic', 'ed', 'en', 'ant', 'ent', 'ar', 'ary'
    ]
    
    adverb_endings = [
        # Adverb endings
        'ly', 'wise', 'ward'
    ]
    
    # Special cases and irregular words
    special_verbs = {
        'be', 'is', 'are', 'was', 'were', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did',
        'sing', 'sang', 'sung', 'go', 'went', 'gone'
    }
    
    # Check special cases first
    if word in special_verbs:
        return 'verb'
    
    # Check verb endings (most specific first)
    if any(word.endswith(ending) for ending in verb_endings):
        return 'verb'
    
    # Check noun endings
    if any(word.endswith(ending) for ending in noun_endings):
        return 'noun'
    
    # Check adjective endings
    if any(word.endswith(ending) for ending in adj_endings):
        return 'adjective'
    
    # Check adverb endings
    if any(word.endswith(ending) for ending in adverb_endings):
        return 'adverb'
    
    # Default classification
    return 'noun'

def migrate_pos():
    add_pos_column()
    
    session = SessionLocal()
    try:
        # Find cards without POS
        cards_without_pos = session.query(Card).filter(Card.pos == None).all()
        
        print(f"Found {len(cards_without_pos)} cards without POS")
        
        # If no cards found, try to update all cards
        if not cards_without_pos:
            cards_without_pos = session.query(Card).all()
        
        for card in cards_without_pos:
            # Only update if pos is None or empty
            if not card.pos:
                card.pos = infer_pos(card.word)
                print(f"Inferred POS for '{card.word}': {card.pos}")
        
        session.commit()
        print("POS migration completed successfully!")
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    migrate_pos()
