import sqlite3
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pos_tagger import POSTagger

class DatabasePOSTagger:
    def __init__(self, db_path):
        self.db_path = db_path
        self.pos_tagger = POSTagger()
    
    def connect_db(self):
        """Connect to the SQLite database"""
        return sqlite3.connect(self.db_path)
    
    def get_table_info(self):
        """Get information about tables in the database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        table_info = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            table_info[table_name] = [col[1] for col in columns]
        
        conn.close()
        return table_info
    
    def get_all_words(self, table_info):
        """Retrieve all unique words from the database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        all_words = set()
        for table, columns in table_info.items():
            for column in columns:
                # Skip columns that are not likely to contain words
                if column.lower() in ['id', 'timestamp', 'pos_tags']:
                    continue
                
                try:
                    cursor.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
                    words = cursor.fetchall()
                    # Split words in case of multi-word entries
                    for word_tuple in words:
                        if word_tuple[0]:
                            # Split by spaces and non-word characters
                            import re
                            split_words = re.findall(r'\b\w+\b', str(word_tuple[0]))
                            all_words.update(split_words)
                except sqlite3.OperationalError as e:
                    print(f"Could not retrieve words from {table}.{column}: {e}")
        
        conn.close()
        return list(all_words)
    
    def tag_words(self, words):
        """Tag words with their possible POS"""
        return {word: self.pos_tagger.tag_pos(word) for word in words}
    
    def update_database_with_pos(self, word_tags):
        """Update database with POS tags"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        # Get all tables
        table_info = self.get_table_info()
        
        for table, columns in table_info.items():
            # Check if pos_tags column exists, if not, add it
            if 'pos_tags' not in columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN pos_tags TEXT")
                except sqlite3.OperationalError:
                    print(f"Could not add pos_tags column to {table}")
            
            # Try to update words with their POS tags in each column
            for column in columns:
                if column.lower() in ['id', 'timestamp', 'pos_tags']:
                    continue
                
                try:
                    # Update words with their POS tags
                    cursor.execute(f"SELECT DISTINCT {column} FROM {table}")
                    entries = cursor.fetchall()
                    
                    for entry in entries:
                        if not entry[0]:
                            continue
                        
                        # Split entry into words
                        import re
                        split_words = re.findall(r'\b\w+\b', str(entry[0]))
                        
                        # Collect POS tags for words
                        pos_tags = {}
                        for word in split_words:
                            pos_tags[word] = ', '.join(word_tags.get(word, ['UNKNOWN']))
                        
                        # Create a string representation of POS tags
                        pos_tags_str = ' | '.join([f"{word}: {tags}" for word, tags in pos_tags.items()])
                        
                        # Update the entry with POS tags
                        cursor.execute(
                            f"UPDATE {table} SET pos_tags = ? WHERE {column} = ?", 
                            (pos_tags_str, entry[0])
                        )
                except sqlite3.OperationalError as e:
                    print(f"Could not update POS tags in {table}.{column}: {e}")
        
        conn.commit()
        conn.close()
    
    def process_database(self):
        """Main method to process the entire database"""
        print("Getting table information...")
        table_info = self.get_table_info()
        print("Tables found:", list(table_info.keys()))
        
        print("Retrieving words...")
        words = self.get_all_words(table_info)
        
        print(f"Tagging {len(words)} unique words...")
        word_tags = self.tag_words(words)
        
        print("Updating database with POS tags...")
        self.update_database_with_pos(word_tags)
        
        print("POS tagging complete!")

def main():
    db_path = 'flashcards.db'
    tagger = DatabasePOSTagger(db_path)
    tagger.process_database()

if __name__ == "__main__":
    main()
