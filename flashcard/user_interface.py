import sys
import os
import json
import getpass
import tkinter as tk
import tkinter.messagebox
from tkinter import simpledialog, ttk, filedialog
from models import UserModel
from datetime import datetime
import configparser
import uuid
from user_management import UserManagement

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
            
            # Use UserManagement to import progress
            user_management = UserManagement()
            success = user_management.import_user_progress(
                guest_file_path, 
                username=username
            )
            
            # Optional: Remove guest progress file after successful conversion
            if success:
                os.remove(guest_file_path)
            
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

class FlashcardLearningApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Flashcard Learning Platform")
        self.master.geometry("800x700")
        self.master.configure(bg='#f0f0f0')
        
        # Initialize UserModel
        self.user_model = UserModel()
        
        # Current logged-in user
        self.current_user = None
        
        # Configuration file path
        self.config_path = os.path.join(os.path.dirname(__file__), 'login_config.ini')
        
        # Create main application window
        self.create_main_window()
    
    def create_main_window(self):
        """
        Create the main application window with feature buttons
        """
        # Clear existing widgets
        for widget in self.master.winfo_children():
            widget.destroy()
        
        # Configure window
        self.master.title("Flashcard Learning Platform")
        self.master.geometry("800x700")
        self.master.configure(bg='#f0f0f0')
        
        # Main frame
        main_frame = tk.Frame(self.master, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title Label
        title_label = tk.Label(
            main_frame, 
            text="Flashcard Learning Platform", 
            font=("Arial", 24, "bold"),
            bg='#f0f0f0',
            fg='#333333'
        )
        title_label.pack(pady=(50, 30))
        
        # Button Frame
        button_frame = tk.Frame(main_frame, bg='#f0f0f0')
        button_frame.pack(expand=True)
        
        # Button Style
        button_style = {
            'font': ('Arial', 14),
            'width': 30,
            'bg': '#FF9800',
            'fg': 'white',
            'activebackground': '#F57C00',
            'activeforeground': 'white',
            'relief': tk.RAISED,
            'borderwidth': 3
        }
        
        # Login Button
        login_button = tk.Button(
            button_frame, 
            text="Login", 
            command=self.login_window,
            bg='#2196F3',
            fg='white',
            **button_style
        )
        login_button.pack(pady=10)
        
        # Register Button
        register_button = tk.Button(
            button_frame, 
            text="Register", 
            command=self.register_window,
            bg='#4CAF50',
            fg='white',
            **button_style
        )
        register_button.pack(pady=10)
        
        # Guest Mode Button
        guest_button = tk.Button(
            button_frame, 
            text="Guest Mode", 
            command=self.guest_mode,
            bg='#FF9800',
            fg='white',
            **button_style
        )
        guest_button.pack(pady=10)
        
        # Features Section
        features_label = tk.Label(
            button_frame, 
            text="Platform Features", 
            font=("Arial", 16, "bold"),
            bg='#f0f0f0'
        )
        features_label.pack(pady=(30, 10))
        
        # Feature Buttons
        features = [
            ("Learning Progress Tracking", self.show_progress_info),
            ("Achievements System", self.show_achievements_info),
            ("Language Learning Goals", self.show_goals_info),
            ("Study Streak Motivation", self.show_streak_info)
        ]
        
        for feature_name, feature_command in features:
            feature_button = tk.Button(
                button_frame, 
                text=feature_name, 
                command=feature_command,
                bg='#FF9800',
                fg='white',
                **button_style
            )
            feature_button.pack(pady=5)
        
        # Optional: Exit Button
        exit_button = tk.Button(
            button_frame, 
            text="Exit", 
            command=self.master.quit,
            bg='#F44336',  # Red color for exit
            fg='white',
            **button_style
        )
        exit_button.pack(pady=(20, 10))
    
    def guest_mode(self):
        """
        Start guest mode with enhanced user experience
        """
        # Create guest session
        self.guest_id = GuestUserManager().create_guest_session()
        
        # Create a dedicated guest mode dashboard
        self.guest_dashboard()

    def guest_dashboard(self):
        """
        Create a specialized dashboard for guest users
        """
        # Clear existing widgets
        for widget in self.master.winfo_children():
            widget.destroy()
        
        # Dashboard Frame
        dashboard_frame = tk.Frame(self.master, bg='#f0f0f0')
        dashboard_frame.pack(fill=tk.BOTH, expand=True)
        
        # Guest Mode Title
        title_label = tk.Label(
            dashboard_frame, 
            text="Guest Learning Mode", 
            font=("Arial", 20, "bold"),
            bg='#f0f0f0',
            fg='#333333'
        )
        title_label.pack(pady=20)
        
        # Guest Session Information
        session_info_frame = tk.Frame(dashboard_frame, bg='#ffffff', padx=20, pady=10)
        session_info_frame.pack(pady=10, fill=tk.X, padx=50)
        
        # Guest Session Details
        session_details = [
            f"Session ID: {self.guest_id[:8]}...",
            "Status: Active Guest Session",
            "Progress: Not Saved Permanently"
        ]
        
        for detail in session_details:
            detail_label = tk.Label(
                session_info_frame, 
                text=detail, 
                font=("Arial", 12),
                bg='#ffffff',
                anchor='w'
            )
            detail_label.pack(pady=5, fill=tk.X)
        
        # Conversion Prompt
        conversion_frame = tk.Frame(dashboard_frame, bg='#f0f0f0')
        conversion_frame.pack(pady=20)
        
        conversion_label = tk.Label(
            conversion_frame,
            text="Want to save your progress permanently?",
            font=("Arial", 14),
            bg='#f0f0f0'
        )
        conversion_label.pack(pady=10)
        
        def open_registration_for_guest():
            """Open registration window with pre-filled guest session context"""
            self.register_window(guest_mode=True, guest_id=self.guest_id)
        
        convert_button = tk.Button(
            conversion_frame, 
            text="Register to Save Progress", 
            command=open_registration_for_guest,
            bg='#4CAF50',
            fg='white',
            font=("Arial", 12)
        )
        convert_button.pack(pady=10)
        
        # Learning Options Frame
        learning_options_frame = tk.Frame(dashboard_frame, bg='#f0f0f0')
        learning_options_frame.pack(pady=20)
        
        learning_options = [
            ("Start Vocabulary Learning", self.start_vocabulary_learning),
            ("Practice Flashcards", self.start_flashcard_practice),
            ("Language Quiz", self.start_language_quiz)
        ]
        
        for label, command in learning_options:
            option_button = tk.Button(
                learning_options_frame, 
                text=label, 
                command=command,
                bg='#2196F3',
                fg='white',
                font=("Arial", 12),
                width=25
            )
            option_button.pack(pady=10)
        
        # Exit Guest Mode Button
        exit_frame = tk.Frame(dashboard_frame, bg='#f0f0f0')
        exit_frame.pack(pady=20)
        
        def exit_guest_mode():
            """Exit guest mode and return to main menu"""
            # Optional: Clear guest session data
            GuestUserManager().clear_guest_session(self.guest_id)
            self.create_main_menu()
        
        exit_button = tk.Button(
            exit_frame, 
            text="Exit Guest Mode", 
            command=exit_guest_mode,
            bg='#FF5722',
            fg='white',
            font=("Arial", 12)
        )
        exit_button.pack()

    def register_window(self, guest_mode=False, guest_id=None):
        """
        Enhanced registration window with optional guest mode conversion
        
        Args:
            guest_mode (bool): Flag to indicate guest mode conversion
            guest_id (str, optional): Guest session ID for conversion
        """
        register_window = tk.Toplevel(self.master)
        register_window.title("Register" + (" - Guest Conversion" if guest_mode else ""))
        register_window.geometry("500x650")
        register_window.configure(bg='#f0f0f0')
        
        # Registration Form (similar to previous implementation)
        # ... [previous registration form code] ...
        
        def register_user():
            username = username_entry.get()
            email = email_entry.get()
            password = password_entry.get()
            confirm_password = confirm_password_entry.get()
            
            # Validation (similar to previous implementation)
            # ... [previous validation code] ...
            
            try:
                # Register user
                user_id = self.user_model.register_user(
                    username, 
                    email, 
                    password, 
                    full_name=full_name_entry.get() or None,
                    language_level=language_level_var.get(),
                    learning_goal=learning_goal_entry.get() or None
                )
                
                # If guest mode, convert guest progress
                if guest_mode and guest_id:
                    conversion_success = self.user_model.convert_guest_to_user(guest_id, username)
                    if conversion_success:
                        messagebox.showinfo(
                            "Progress Saved", 
                            f"Welcome {username}! Your guest learning progress has been saved."
                        )
                
                messagebox.showinfo("Registration Successful", f"User registered with ID: {user_id}")
                register_window.destroy()
                
                # Proceed to user dashboard
                self.current_user = {
                    'username': username,
                    'email': email,
                    # Add other user details as needed
                }
                self.user_dashboard()
            
            except ValueError as e:
                messagebox.showerror("Registration Failed", str(e))

        # Register Button
        register_button = tk.Button(
            register_window, 
            text="Register" + (" & Save Progress" if guest_mode else ""), 
            command=register_user,
            width=20,
            bg='#2196F3',
            fg='white'
        )
        register_button.pack(pady=20)

        # Add back button
        self.add_back_button(self.master, register_window)

    def start_vocabulary_learning(self):
        """
        Start vocabulary learning module for guest or registered users
        """
        vocab_window = tk.Toplevel(self.master)
        vocab_window.title("Vocabulary Learning")
        vocab_window.geometry("600x500")
        vocab_window.configure(bg='#f0f0f0')
        
        # Vocabulary Learning Title
        title_label = tk.Label(
            vocab_window, 
            text="Vocabulary Learning", 
            font=("Arial", 18, "bold"),
            bg='#f0f0f0'
        )
        title_label.pack(pady=20)
        
        # Difficulty Selection
        difficulty_frame = tk.Frame(vocab_window, bg='#f0f0f0')
        difficulty_frame.pack(pady=10)
        
        difficulty_label = tk.Label(
            difficulty_frame, 
            text="Select Difficulty:", 
            font=("Arial", 12),
            bg='#f0f0f0'
        )
        difficulty_label.pack(side=tk.LEFT, padx=10)
        
        difficulty_var = tk.StringVar(vocab_window)
        difficulty_var.set("Beginner")
        
        difficulty_options = ["Beginner", "Intermediate", "Advanced"]
        difficulty_dropdown = ttk.Combobox(
            difficulty_frame, 
            textvariable=difficulty_var, 
            values=difficulty_options,
            state="readonly",
            width=15
        )
        difficulty_dropdown.pack(side=tk.LEFT)
        
        # Learning Area
        learning_frame = tk.Frame(vocab_window, bg='#ffffff', padx=20, pady=20)
        learning_frame.pack(pady=20, padx=50, fill=tk.BOTH, expand=True)
        
        # Placeholder for vocabulary content
        vocab_label = tk.Label(
            learning_frame, 
            text="Vocabulary learning content will be loaded here.",
            font=("Arial", 12),
            bg='#ffffff',
            wrap=True
        )
        vocab_label.pack(expand=True)
        
        # Progress Tracking
        progress_frame = tk.Frame(vocab_window, bg='#f0f0f0')
        progress_frame.pack(pady=10)
        
        progress_label = tk.Label(
            progress_frame, 
            text="Words Learned: 0 | Current Streak: 0 days", 
            font=("Arial", 10),
            bg='#f0f0f0'
        )
        progress_label.pack()
        
        # Save Progress Button
        def save_progress():
            """Save learning progress for guest or registered user"""
            if hasattr(self, 'guest_id'):
                # Guest mode progress saving
                GuestUserManager().save_guest_progress(
                    self.guest_id, 
                    {
                        'words_learned': 5,  # Placeholder
                        'study_duration': 15,  # Placeholder
                        'difficulty_level': difficulty_var.get()
                    }
                )
            else:
                # Registered user progress saving
                # Implement user progress saving logic
                pass
        
            messagebox.showinfo("Progress Saved", "Your learning progress has been saved!")
        
        save_button = tk.Button(
            vocab_window, 
            text="Save Progress", 
            command=save_progress,
            bg='#4CAF50',
            fg='white'
        )
        save_button.pack(pady=10)

        # Add back button
        self.add_back_button(self.master, vocab_window)

    def start_flashcard_practice(self):
        """
        Start flashcard practice module for guest or registered users
        """
        flashcard_window = tk.Toplevel(self.master)
        flashcard_window.title("Flashcard Practice")
        flashcard_window.geometry("600x500")
        flashcard_window.configure(bg='#f0f0f0')
        
        # Flashcard Practice Title
        title_label = tk.Label(
            flashcard_window, 
            text="Flashcard Practice", 
            font=("Arial", 18, "bold"),
            bg='#f0f0f0'
        )
        title_label.pack(pady=20)
        
        # Placeholder for flashcard content
        flashcard_label = tk.Label(
            flashcard_window, 
            text="Flashcard practice interface will be implemented here.",
            font=("Arial", 12),
            bg='#f0f0f0',
            wrap=True
        )
        flashcard_label.pack(expand=True)

        # Add back button
        self.add_back_button(self.master, flashcard_window)

    def start_language_quiz(self):
        """
        Start language quiz module for guest or registered users
        """
        quiz_window = tk.Toplevel(self.master)
        quiz_window.title("Language Quiz")
        quiz_window.geometry("600x500")
        quiz_window.configure(bg='#f0f0f0')
        
        # Language Quiz Title
        title_label = tk.Label(
            quiz_window, 
            text="Language Quiz", 
            font=("Arial", 18, "bold"),
            bg='#f0f0f0'
        )
        title_label.pack(pady=20)
        
        # Placeholder for quiz content
        quiz_label = tk.Label(
            quiz_window, 
            text="Language quiz interface will be developed here.",
            font=("Arial", 12),
            bg='#f0f0f0',
            wrap=True
        )
        quiz_label.pack(expand=True)

        # Add back button
        self.add_back_button(self.master, quiz_window)

    def show_progress_info(self):
        """
        Display detailed learning progress information
        """
        # Create a new window for progress tracking
        progress_window = tk.Toplevel(self.master)
        progress_window.title("Learning Progress Tracking")
        progress_window.geometry("600x500")
        progress_window.configure(bg='#f0f0f0')

        # Progress Tracking Frame
        progress_frame = tk.Frame(progress_window, bg='#ffffff', padx=20, pady=20)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Title
        title_label = tk.Label(
            progress_frame, 
            text="Your Learning Progress", 
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#333333'
        )
        title_label.pack(pady=(0, 20))

        # Simulated Progress Data (replace with actual data retrieval)
        progress_data = {
            "Total Cards Learned": 150,
            "Cards in Progress": 50,
            "Mastery Level": "Intermediate",
            "Study Time": "12 hours 45 minutes",
            "Last Study Session": "2 hours ago"
        }

        # Display Progress Details
        for key, value in progress_data.items():
            detail_frame = tk.Frame(progress_frame, bg='#ffffff')
            detail_frame.pack(fill=tk.X, pady=5)

            label_key = tk.Label(
                detail_frame, 
                text=f"{key}:", 
                font=("Arial", 12, "bold"),
                bg='#ffffff',
                anchor='w',
                width=20
            )
            label_key.pack(side=tk.LEFT)

            label_value = tk.Label(
                detail_frame, 
                text=value, 
                font=("Arial", 12),
                bg='#ffffff',
                anchor='w'
            )
            label_value.pack(side=tk.LEFT)

        # Progress Bar (Visual Representation)
        progress_bar_frame = tk.Frame(progress_frame, bg='#ffffff')
        progress_bar_frame.pack(fill=tk.X, pady=(20, 0))

        progress_label = tk.Label(
            progress_bar_frame, 
            text="Overall Progress", 
            font=("Arial", 12, "bold"),
            bg='#ffffff'
        )
        progress_label.pack()

        canvas = tk.Canvas(
            progress_bar_frame, 
            width=500, 
            height=30, 
            bg='#f0f0f0', 
            highlightthickness=0
        )
        canvas.pack(pady=10)

        # Draw progress bar
        canvas.create_rectangle(0, 0, 500, 30, fill='#e0e0e0', outline='')
        canvas.create_rectangle(0, 0, 350, 30, fill='#4CAF50', outline='')

        percentage_label = tk.Label(
            progress_bar_frame, 
            text="70% Complete", 
            font=("Arial", 10),
            bg='#ffffff'
        )
        percentage_label.pack()

        # Add back button
        self.add_back_button(self.master, progress_window)

    def show_achievements_info(self):
        """
        Display user achievements and milestones
        """
        # Create achievements window
        achievements_window = tk.Toplevel(self.master)
        achievements_window.title("Achievements System")
        achievements_window.geometry("600x500")
        achievements_window.configure(bg='#f0f0f0')

        # Achievements Frame
        achievements_frame = tk.Frame(achievements_window, bg='#ffffff', padx=20, pady=20)
        achievements_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Title
        title_label = tk.Label(
            achievements_frame, 
            text="Your Achievements", 
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#333333'
        )
        title_label.pack(pady=(0, 20))

        # Simulated Achievements Data
        achievements_data = [
            {"name": "Vocabulary Novice", "description": "Learned first 50 words", "status": "Completed"},
            {"name": "Language Explorer", "description": "Study for 7 consecutive days", "status": "In Progress"},
            {"name": "Pronunciation Master", "description": "Perfect pronunciation for 100 words", "status": "Not Started"},
            {"name": "Grammar Guru", "description": "Complete 5 grammar quizzes", "status": "In Progress"}
        ]

        # Display Achievements
        for achievement in achievements_data:
            achievement_frame = tk.Frame(achievements_frame, bg='#ffffff', relief=tk.RAISED, borderwidth=1)
            achievement_frame.pack(fill=tk.X, pady=5)

            name_label = tk.Label(
                achievement_frame, 
                text=achievement['name'], 
                font=("Arial", 12, "bold"),
                bg='#ffffff',
                anchor='w',
                width=20
            )
            name_label.pack(side=tk.LEFT, padx=10, pady=5)

            desc_label = tk.Label(
                achievement_frame, 
                text=achievement['description'], 
                font=("Arial", 10),
                bg='#ffffff',
                anchor='w'
            )
            desc_label.pack(side=tk.LEFT, padx=10, pady=5)

            status_label = tk.Label(
                achievement_frame, 
                text=achievement['status'], 
                font=("Arial", 10, "bold"),
                fg='green' if achievement['status'] == 'Completed' else 'orange',
                bg='#ffffff'
            )
            status_label.pack(side=tk.RIGHT, padx=10, pady=5)

        # Add back button
        self.add_back_button(self.master, achievements_window)

    def show_goals_info(self):
        """
        Display and manage language learning goals
        """
        # Create goals window
        goals_window = tk.Toplevel(self.master)
        goals_window.title("Language Learning Goals")
        goals_window.geometry("600x500")
        goals_window.configure(bg='#f0f0f0')

        # Goals Frame
        goals_frame = tk.Frame(goals_window, bg='#ffffff', padx=20, pady=20)
        goals_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Title
        title_label = tk.Label(
            goals_frame, 
            text="Your Learning Goals", 
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#333333'
        )
        title_label.pack(pady=(0, 20))

        # Simulated Goals Data
        goals_data = [
            {"goal": "Learn 500 Vocabulary Words", "progress": 250, "total": 500},
            {"goal": "Complete Advanced Grammar Course", "progress": 3, "total": 10},
            {"goal": "Improve Pronunciation", "progress": 60, "total": 100}
        ]

        # Display Goals
        for goal in goals_data:
            goal_frame = tk.Frame(goals_frame, bg='#ffffff')
            goal_frame.pack(fill=tk.X, pady=10)

            goal_label = tk.Label(
                goal_frame, 
                text=goal['goal'], 
                font=("Arial", 12, "bold"),
                bg='#ffffff',
                anchor='w'
            )
            goal_label.pack(side=tk.TOP, anchor='w')

            progress_canvas = tk.Canvas(
                goal_frame, 
                width=500, 
                height=20, 
                bg='#f0f0f0', 
                highlightthickness=0
            )
            progress_canvas.pack(pady=5)

            # Calculate percentage
            percentage = (goal['progress'] / goal['total']) * 100
            progress_canvas.create_rectangle(0, 0, 500, 20, fill='#e0e0e0', outline='')
            progress_canvas.create_rectangle(0, 0, percentage * 5, 20, fill='#2196F3', outline='')

            progress_label = tk.Label(
                goal_frame, 
                text=f"{goal['progress']}/{goal['total']} ({percentage:.1f}%)", 
                font=("Arial", 10),
                bg='#ffffff'
            )
            progress_label.pack(side=tk.BOTTOM, anchor='w')

        # Add Goal Button
        add_goal_button = tk.Button(
            goals_frame, 
            text="Add New Goal", 
            command=self.add_new_goal,
            bg='#4CAF50',
            fg='white'
        )
        add_goal_button.pack(pady=(20, 0))

        # Add back button
        self.add_back_button(self.master, goals_window)

    def add_new_goal(self):
        """
        Open a dialog to add a new learning goal
        """
        goal_dialog = tk.Toplevel(self.master)
        goal_dialog.title("Add New Goal")
        goal_dialog.geometry("400x300")

        # Goal Type Selection
        type_label = tk.Label(goal_dialog, text="Goal Type:")
        type_label.pack(pady=(20, 5))
        goal_types = ["Vocabulary", "Grammar", "Pronunciation", "Listening", "Speaking"]
        goal_type_var = tk.StringVar(goal_dialog)
        goal_type_var.set(goal_types[0])
        goal_type_menu = tk.OptionMenu(goal_dialog, goal_type_var, *goal_types)
        goal_type_menu.pack(pady=5)

        # Goal Target
        target_label = tk.Label(goal_dialog, text="Target Number:")
        target_label.pack(pady=(10, 5))
        target_entry = tk.Entry(goal_dialog)
        target_entry.pack(pady=5)

        # Deadline
        deadline_label = tk.Label(goal_dialog, text="Deadline (optional):")
        deadline_label.pack(pady=(10, 5))
        deadline_entry = tk.Entry(goal_dialog)
        deadline_entry.pack(pady=5)

        # Save Goal Button
        def save_goal():
            # Here you would typically save the goal to a database or file
            goal_type = goal_type_var.get()
            target = target_entry.get()
            deadline = deadline_entry.get()
            
            # Simple validation
            if target and target.isdigit():
                tk.messagebox.showinfo("Goal Added", f"New {goal_type} goal set: {target}")
                goal_dialog.destroy()
            else:
                tk.messagebox.showerror("Invalid Input", "Please enter a valid target number")

        save_button = tk.Button(goal_dialog, text="Save Goal", command=save_goal)
        save_button.pack(pady=(20, 0))

        # Add back button
        self.add_back_button(self.master, goal_dialog)

    def show_streak_info(self):
        """
        Display study streak motivation and details
        """
        # Create streak window
        streak_window = tk.Toplevel(self.master)
        streak_window.title("Study Streak Motivation")
        streak_window.geometry("600x500")
        streak_window.configure(bg='#f0f0f0')

        # Streak Frame
        streak_frame = tk.Frame(streak_window, bg='#ffffff', padx=20, pady=20)
        streak_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Title
        title_label = tk.Label(
            streak_frame, 
            text="Your Study Streak", 
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#333333'
        )
        title_label.pack(pady=(0, 20))

        # Streak Details
        streak_details = {
            "Current Streak": "12 days",
            "Longest Streak": "45 days",
            "Last Study Date": "Today",
            "Consecutive Days": "12"
        }

        # Streak Visualization
        streak_canvas = tk.Canvas(
            streak_frame, 
            width=500, 
            height=100, 
            bg='#f0f0f0', 
            highlightthickness=0
        )
        streak_canvas.pack(pady=(0, 20))

        # Draw streak calendar-like visualization
        day_width = 40
        for i in range(14):  # Last 14 days
            color = '#4CAF50' if i < 12 else '#e0e0e0'  # Green for streak days, gray for missed days
            streak_canvas.create_rectangle(
                i * day_width, 0, 
                (i + 1) * day_width, 100, 
                fill=color, 
                outline='white'
            )
            # Add day number
            streak_canvas.create_text(
                i * day_width + day_width // 2, 50, 
                text=str(14 - i), 
                font=("Arial", 12)
            )

        # Display Streak Details
        for key, value in streak_details.items():
            detail_frame = tk.Frame(streak_frame, bg='#ffffff')
            detail_frame.pack(fill=tk.X, pady=5)

            label_key = tk.Label(
                detail_frame, 
                text=f"{key}:", 
                font=("Arial", 12, "bold"),
                bg='#ffffff',
                anchor='w',
                width=20
            )
            label_key.pack(side=tk.LEFT)

            label_value = tk.Label(
                detail_frame, 
                text=value, 
                font=("Arial", 12),
                bg='#ffffff',
                anchor='w'
            )
            label_value.pack(side=tk.LEFT)

        # Motivation Message
        motivation_label = tk.Label(
            streak_frame, 
            text="Keep up the great work! Maintain your streak to become a language master.", 
            font=("Arial", 10, "italic"),
            bg='#ffffff',
            wraplength=500,
            justify=tk.CENTER
        )
        motivation_label.pack(pady=(20, 0))

        # Add back button
        self.add_back_button(self.master, streak_window)

    def add_back_button(self, parent_window, current_window):
        """
        Add a back button to the given window that returns to the previous screen
        
        Args:
            parent_window (tk.Tk or tk.Toplevel): The main application window
            current_window (tk.Toplevel): The current window to add the back button to
        """
        # Create a frame for the back button
        back_frame = tk.Frame(current_window, bg='#f0f0f0')
        back_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)

        # Back button style
        back_button_style = {
            'font': ('Arial', 12),
            'bg': '#FF9800',  # Orange background
            'fg': 'white',    # White text
            'activebackground': '#F57C00',  # Darker orange when pressed
            'activeforeground': 'white',
            'relief': tk.RAISED,
            'borderwidth': 3
        }

        # Create back button
        back_button = tk.Button(
            back_frame, 
            text="← Back to Main Menu", 
            command=lambda: self.return_to_main_menu(current_window),
            **back_button_style
        )
        back_button.pack(pady=10)

    def return_to_main_menu(self, current_window):
        """
        Return to the main menu by destroying the current window
        and recreating the main window
        
        Args:
            current_window (tk.Toplevel): The current window to be closed
        """
        # Close the current window
        if current_window:
            current_window.destroy()
        
        # Recreate main window
        self.create_main_window()

def login_page():
    """
    Placeholder login page function
    
    Returns:
        str: Rendered login template or login logic
    """
    return "Login Page"

def register_page():
    """
    Placeholder register page function
    
    Returns:
        str: Rendered register template or registration logic
    """
    return "Register Page"

def create_login_template():
    """
    Create a login HTML template
    
    Returns:
        str: HTML template for login page
    """
    login_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login</title>
</head>
<body>
    <h1>Login Page</h1>
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
</body>
</html>
'''
    return login_template

def create_register_template():
    """
    Create a register HTML template
    
    Returns:
        str: HTML template for register page
    """
    register_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Register</title>
</head>
<body>
    <h1>Register Page</h1>
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="password" name="confirm_password" placeholder="Confirm Password" required>
        <button type="submit">Register</button>
    </form>
</body>
</html>
'''
    return register_template
