import sys
import getpass
from datetime import datetime
import sqlite3
import json
import os

from models import UserModel

class UserManagement:
    def __init__(self):
        self.user_model = UserModel()
        
        # Ensure users table exists
        self.user_model.create_user_table()
    
    def register(self, username=None, email=None, password=None):
        """Interactive or programmatic user registration"""
        if not username:
            print("=== User Registration ===")
            username = input("Choose a username: ").strip()
        if not email:
            email = input("Enter your email: ").strip()
        
        # Securely get password
        if not password:
            while True:
                password = getpass.getpass("Choose a password: ")
                confirm_password = getpass.getpass("Confirm password: ")
                
                if password != confirm_password:
                    print("Passwords do not match. Please try again.")
                    continue
                
                break
        
        try:
            user_id = self.user_model.register_user(username, email, password)
            print(f"Registration successful! Your user ID is {user_id}")
            return username
        except ValueError as e:
            print(f"Registration failed: {e}")
            return None
    
    def login(self, username=None, password=None):
        """Interactive or programmatic user login"""
        if not username:
            print("=== User Login ===")
            username = input("Username: ").strip()
        
        if not password:
            password = getpass.getpass("Password: ")
        
        if self.user_model.authenticate_user(username, password):
            print(f"Welcome back, {username}!")
            return username
        else:
            print("Login failed. Invalid username or password.")
            return None
    
    def view_progress(self, username):
        """View user's learning progress"""
        progress = self.user_model.get_user_progress(username)
        
        if progress:
            words_learned, study_time, current_streak, max_streak, last_login = progress
            print("\n=== Learning Progress ===")
            print(f"Total Words Learned: {words_learned}")
            print(f"Total Study Time: {study_time} seconds")
            print(f"Current Study Streak: {current_streak}")
            print(f"Maximum Study Streak: {max_streak}")
            print(f"Last Login: {last_login}")
        else:
            print("No progress data found.")
    
    def update_progress(self, username, words_learned=0, study_time=0):
        """Update user's learning progress"""
        self.user_model.update_learning_progress(username, words_learned, study_time)
        print("Progress updated successfully!")
    
    def export_user_progress(self, username, export_path=None):
        """
        Export user's learning progress to a JSON file
        
        Args:
            username (str): Username to export progress for
            export_path (str, optional): Custom export path. Defaults to user's home directory.
        
        Returns:
            str: Path to exported file
        """
        session = self.user_model._get_connection()
        
        try:
            # Find user
            user = session.query(User).filter_by(username=username).first()
            if not user:
                raise ValueError(f"User {username} not found")
            
            # Prepare export data
            export_data = {
                "user_info": {
                    "username": user.username,
                    "email": user.email,
                    "language_level": user.language_level,
                    "learning_goal": user.learning_goal
                },
                "learning_stats": {
                    "total_words_learned": user.total_words_learned,
                    "total_study_time": user.total_study_time,
                    "current_streak": user.current_streak,
                    "max_streak": user.max_streak
                },
                "learning_progress": [
                    {
                        "session_date": progress.session_date.isoformat(),
                        "study_duration": progress.study_duration,
                        "words_learned": progress.words_learned,
                        "words_reviewed": progress.words_reviewed,
                        "topic": progress.topic,
                        "difficulty_level": progress.difficulty_level,
                        "accuracy_rate": progress.accuracy_rate
                    } for progress in user.learning_progress
                ]
            }
            
            # Determine export path
            if not export_path:
                export_path = os.path.join(
                    os.path.expanduser("~"), 
                    f"{username}_learning_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
            
            # Export to JSON
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
            
            print(f"User progress exported successfully to {export_path}")
            return export_path
        
        finally:
            session.close()

    def import_user_progress(self, import_path, username=None):
        """
        Import user's learning progress from a JSON file
        
        Args:
            import_path (str): Path to the JSON file with learning progress
            username (str, optional): Username to import for. If not provided, uses username from file.
        
        Returns:
            bool: Import success status
        """
        session = self.user_model._get_connection()
        
        try:
            # Read import file
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Determine username
            if not username:
                username = import_data['user_info']['username']
            
            # Find or create user
            user = session.query(User).filter_by(username=username).first()
            if not user:
                # If user doesn't exist, create a new one
                user = User(
                    username=username,
                    email=import_data['user_info'].get('email', f"{username}@example.com"),
                    language_level=import_data['user_info'].get('language_level', 'Beginner')
                )
                session.add(user)
            
            # Update user stats
            stats = import_data['learning_stats']
            user.total_words_learned = stats.get('total_words_learned', 0)
            user.total_study_time = stats.get('total_study_time', 0.0)
            user.current_streak = stats.get('current_streak', 0)
            user.max_streak = stats.get('max_streak', 0)
            user.learning_goal = import_data['user_info'].get('learning_goal', '')
            
            # Import learning progress
            for progress_data in import_data['learning_progress']:
                progress = LearningProgress(
                    user_id=user.id,
                    session_date=datetime.fromisoformat(progress_data['session_date']),
                    study_duration=progress_data.get('study_duration', 0.0),
                    words_learned=progress_data.get('words_learned', 0),
                    words_reviewed=progress_data.get('words_reviewed', 0),
                    topic=progress_data.get('topic'),
                    difficulty_level=progress_data.get('difficulty_level'),
                    accuracy_rate=progress_data.get('accuracy_rate', 0.0)
                )
                session.add(progress)
            
            session.commit()
            print(f"User progress for {username} imported successfully")
            return True
        
        except Exception as e:
            session.rollback()
            print(f"Error importing progress: {e}")
            return False
        
        finally:
            session.close()

    def start_guest_session(self):
        """
        Start a new guest learning session
        
        Returns:
            str: Guest session ID
        """
        guest_manager = GuestUserManager()
        return guest_manager.create_guest_session()

    def save_guest_progress(self, guest_id, study_data):
        """
        Save progress for a guest session
        
        Args:
            guest_id (str): Guest session ID
            study_data (dict): Learning progress data
        """
        guest_manager = GuestUserManager()
        guest_manager.save_guest_progress(guest_id, study_data)

    def convert_guest_to_user(self, guest_id, username):
        """
        Convert guest progress to a registered user account
        
        Args:
            guest_id (str): Guest session ID
            username (str): Username to convert to
        
        Returns:
            bool: Conversion success status
        """
        guest_manager = GuestUserManager()
        return guest_manager.convert_guest_to_user(guest_id, username)

class GuestUserManager:
    """
    Manages guest user sessions and temporary progress tracking
    """
    def __init__(self, storage_dir='guest_progress'):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
    
    def create_guest_session(self):
        """
        Create a new guest session with a unique identifier
        
        Returns:
            str: Guest session ID
        """
        guest_id = str(uuid.uuid4())
        guest_file_path = os.path.join(self.storage_dir, f"{guest_id}_progress.json")
        
        # Initialize guest progress file
        initial_progress = {
            "session_id": guest_id,
            "created_at": datetime.now().isoformat(),
            "learning_stats": {
                "total_words_learned": 0,
                "total_study_time": 0.0,
                "sessions_completed": 0
            },
            "learning_progress": []
        }
        
        with open(guest_file_path, 'w') as f:
            json.dump(initial_progress, f, indent=4)
        
        return guest_id
    
    def save_guest_progress(self, guest_id, study_data):
        """
        Save learning progress for a guest session
        
        Args:
            guest_id (str): Guest session ID
            study_data (dict): Learning progress data
        """
        guest_file_path = os.path.join(self.storage_dir, f"{guest_id}_progress.json")
        
        try:
            with open(guest_file_path, 'r') as f:
                guest_progress = json.load(f)
            
            # Update learning stats
            guest_progress['learning_stats']['total_words_learned'] += study_data.get('words_learned', 0)
            guest_progress['learning_stats']['total_study_time'] += study_data.get('study_duration', 0.0)
            guest_progress['learning_stats']['sessions_completed'] += 1
            
            # Add current session progress
            guest_progress['learning_progress'].append({
                "session_date": datetime.now().isoformat(),
                **study_data
            })
            
            with open(guest_file_path, 'w') as f:
                json.dump(guest_progress, f, indent=4)
        
        except FileNotFoundError:
            print(f"Guest session {guest_id} not found.")
    
    def convert_guest_to_user(self, guest_id, username):
        """
        Convert guest progress to a registered user account
        
        Args:
            guest_id (str): Guest session ID
            username (str): Username to convert to
        
        Returns:
            bool: Conversion success status
        """
        guest_file_path = os.path.join(self.storage_dir, f"{guest_id}_progress.json")
        
        try:
            with open(guest_file_path, 'r') as f:
                guest_progress = json.load(f)
            
            # Create a temporary file for import
            import_file_path = os.path.join(self.storage_dir, f"{username}_imported_progress.json")
            with open(import_file_path, 'w') as f:
                json.dump(guest_progress, f, indent=4)
            
            # Use import_user_progress method
            from models import UserModel
            user_model = UserModel()
            success = user_model.import_user_progress(import_file_path, username=username)
            
            # Optional: Remove guest and import files after successful conversion
            if success:
                os.remove(guest_file_path)
                os.remove(import_file_path)
            
            return success
        
        except Exception as e:
            print(f"Error converting guest progress: {e}")
            return False
    
    def clear_guest_session(self, guest_id):
        """
        Clear guest session data
        
        Args:
            guest_id (str): Guest session ID to clear
        """
        guest_file_path = os.path.join(self.storage_dir, f"{guest_id}_progress.json")
        
        try:
            if os.path.exists(guest_file_path):
                os.remove(guest_file_path)
            print(f"Guest session {guest_id} cleared successfully")
        except Exception as e:
            print(f"Error clearing guest session: {e}")

def interactive_demo():
    """Interactive user management demo with enhanced features"""
    print("\n=== Flashcard Learning App Demo ===")
    
    # Initialize UserModel
    user_model = UserModel()
    
    # Predefined demo user for automated testing
    demo_username = 'johndoe'
    demo_email = 'john@example.com'
    demo_password = 'SecurePass123!'
    
    try:
        # Attempt to register demo user, handle existing user
        try:
            user_id = user_model.register_user(
                demo_username, 
                demo_email, 
                demo_password, 
                full_name='John Doe',
                language_level='Intermediate',
                learning_goal='Become fluent in English'
            )
            print(f"User registered with ID: {user_id}")
        except ValueError as e:
            # If user already exists, just proceed
            print(f"User already exists: {e}")
        
        # Update learning progress
        user_model.update_learning_progress(demo_username, words_learned=50, study_time=1800)
        
        # Add an achievement
        user_model.add_achievement(
            demo_username, 
            'Word Warrior', 
            'Learned 50 words in a single session', 
            10
        )
        
        # Retrieve and display achievements
        achievements = user_model.get_user_achievements(demo_username)
        print("\nUser Achievements:")
        for achievement in achievements:
            print(f"- {achievement[0]}: {achievement[1]} (Earned on {achievement[2]}, Points: {achievement[3]})")
        
        # Display user progress
        progress = user_model.get_user_progress(demo_username)
        print("\n=== Learning Progress ===")
        print(f"Total Words Learned: {progress[0]}")
        print(f"Total Study Time: {progress[1]} seconds")
        print(f"Current Study Streak: {progress[2]}")
        print(f"Maximum Study Streak: {progress[3]}")
        print(f"Last Login: {progress[4]}")
        print(f"Full Name: {progress[5] or 'Not Set'}")
        print(f"Language Level: {progress[6] or 'Not Set'}")
        print(f"Learning Goal: {progress[7] or 'Not Set'}")
        print(f"Total Achievements: {progress[8]}")
        print(f"Achievement Points: {progress[9]}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    interactive_demo()

if __name__ == "__main__":
    main()
