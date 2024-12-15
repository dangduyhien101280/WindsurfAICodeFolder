const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const path = require('path');

const app = express();
const dbPath = path.join(__dirname, 'flashcards.db'); // Update with your database path
const db = new sqlite3.Database(dbPath);

app.use(cors());
app.use(express.json());

// Serve the index.html file from the templates directory
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

// Endpoint to get all flashcards
app.get('/api/cards', (req, res) => {
    const query = `SELECT id, word, vietnamese_translation, chinese, japanese, example, ipa, box_number, created_at, pos, last_reviewed, meaning, next_review, updated_at FROM cards`;
    db.all(query, [], (err, rows) => {
        if (err) {
            console.error('Database error:', err);
            res.status(500).send(err.message);
        } else {
            res.json(rows);
        }
    });
});

const PORT = 5000;
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});