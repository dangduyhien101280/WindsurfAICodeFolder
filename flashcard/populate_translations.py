import sqlite3
from googletrans import Translator

def column_exists(cursor, column_name):
    cursor.execute("PRAGMA table_info(cards);")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def populate_translations(db_path):
    translator = Translator()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Thêm cột cho tiếng Trung giản thể, Pinyin, tiếng Nhật và Hiragana nếu chưa tồn tại
    if not column_exists(cursor, 'chinese'):
        cursor.execute("ALTER TABLE cards ADD COLUMN chinese TEXT;")
    if not column_exists(cursor, 'pinyin'):
        cursor.execute("ALTER TABLE cards ADD COLUMN pinyin TEXT;")
    if not column_exists(cursor, 'vietnamese_translation'):
        cursor.execute("ALTER TABLE cards ADD COLUMN vietnamese_translation TEXT;")
    if not column_exists(cursor, 'japanese'):
        cursor.execute("ALTER TABLE cards ADD COLUMN japanese TEXT;")
    if not column_exists(cursor, 'hiragana'):
        cursor.execute("ALTER TABLE cards ADD COLUMN hiragana TEXT;")

    # Fetch all words from the cards table
    cursor.execute('SELECT id, word FROM cards')
    rows = cursor.fetchall()
    
    # Dịch từng từ và cập nhật cơ sở dữ liệu
    for row in rows:
        id, english_word = row
        try:
            # Dịch từ tiếng Anh sang tiếng Trung giản thể
            chinese_translation = translator.translate(english_word, src='en', dest='zh-cn')
            chinese_word = chinese_translation.text
            
            # Kiểm tra lỗi và lấy Pinyin
            pinyin = chinese_translation.pronunciation if hasattr(chinese_translation, 'pronunciation') else 'N/A'
            
            # Dịch sang tiếng Việt
            vietnamese_translation = translator.translate(english_word, dest='vi').text
            
            # Dịch sang tiếng Nhật
            japanese_translation = translator.translate(english_word, dest='ja').text
            hiragana = japanese_translation.pronunciation if hasattr(japanese_translation, 'pronunciation') else 'N/A'
            
            # Cập nhật cơ sở dữ liệu với các bản dịch
            cursor.execute("UPDATE cards SET vietnamese_translation = ?, chinese = ?, pinyin = ?, japanese = ?, hiragana = ? WHERE id = ?", (vietnamese_translation, chinese_word, pinyin, japanese_translation, hiragana, id))
        except Exception as e:
            # Ghi lại lỗi nếu có
            print(f'Error translating word {english_word} (ID {id}): {e}')
    
    conn.commit()
    conn.close()
    print('Translations populated successfully.')

if __name__ == '__main__':
    populate_translations('flashcards.db')
