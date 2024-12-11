import sqlite3
import sys

def display_pos_tagged_words(db_path, limit=50):
    """
    Display POS tagged words from the database
    
    Args:
        db_path (str): Path to the SQLite database
        limit (int): Number of words to display
    """
    # Ensure proper Unicode handling
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table information
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("=== POS Tagged Words ===")
    for table in tables:
        table_name = table[0]
        print(f"\n--- Table: {table_name} ---")
        
        # Get columns in the table
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        # Find columns that might contain text
        text_columns = [
            col[1] for col in columns 
            if col[1].lower() not in ['id', 'timestamp', 'pos_tags']
        ]
        
        # If no text columns found, continue
        if not text_columns:
            print("No text columns found.")
            continue
        
        # Query to get entries with POS tags
        query = f"""
        SELECT {', '.join(text_columns)}, pos_tags 
        FROM {table_name} 
        WHERE pos_tags IS NOT NULL 
        LIMIT {limit}
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Display results
        if not results:
            print("No POS tagged entries found.")
            continue
        
        # Print column headers
        headers = text_columns + ['POS Tags']
        print(' | '.join(headers))
        print('-' * 80)
        
        # Print each result
        for result in results:
            # Convert result to strings, handling potential None values
            str_result = [str(item) if item is not None else 'N/A' for item in result]
            
            # Safely print with Unicode support
            try:
                print(' | '.join(str_result))
            except UnicodeEncodeError:
                # Fallback: print with error handling
                safe_result = [
                    item.encode('ascii', 'ignore').decode('ascii') 
                    if isinstance(item, str) else str(item) 
                    for item in str_result
                ]
                print(' | '.join(safe_result))
    
    conn.close()

def main():
    db_path = 'flashcards.db'
    display_pos_tagged_words(db_path)

if __name__ == "__main__":
    main()
