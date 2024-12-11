import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('flashcards.db')
cursor = conn.cursor()

# Query to fetch all flashcards
query = "SELECT * FROM cards;"
cursor.execute(query)

# Fetch all results
flashcards = cursor.fetchall()

# Write the results to a file
with open('flashcards_output.txt', 'w', encoding='utf-8') as f:
    for card in flashcards:
        f.write(', '.join(str(item) for item in card) + '\n')

# Close the connection
conn.close()
