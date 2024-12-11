import sqlite3
from datetime import datetime, timedelta
import hashlib
import uuid
import re
import os

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Sử dụng declarative_base() cho SQLAlchemy 2.0
Base = declarative_base()

class User(Base):
    """
    User model cho hệ thống học từ vựng
    Lưu trữ thông tin người dùng và tiến trình học tập
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_salt = Column(String(100), nullable=False)
    password_hash = Column(String(256), nullable=False)
    
    # Thông tin cá nhân
    full_name = Column(String(100), nullable=True)
    language_level = Column(String(50), nullable=True, default='Beginner')
    learning_goal = Column(String(200), nullable=True)
    
    # Thống kê học tập
    total_words_learned = Column(Integer, default=0)
    total_study_time = Column(Float, default=0.0)  # Tổng thời gian học (phút)
    current_streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    
    # Thành tích
    total_achievements = Column(Integer, default=0)
    achievement_points = Column(Integer, default=0)
    
    # Mối quan hệ với bảng Achievements
    achievements = relationship('Achievement', back_populates='user', cascade='all, delete-orphan')
    
    # Mối quan hệ với bảng LearningProgress
    learning_progress = relationship('LearningProgress', back_populates='user', cascade='all, delete-orphan')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Achievement(Base):
    """
    Model lưu trữ các thành tích của người dùng
    """
    __tablename__ = 'achievements'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    achievement_name = Column(String(100), nullable=False)
    achievement_description = Column(Text, nullable=True)
    points = Column(Integer, default=0)
    date_earned = Column(DateTime, default=datetime.utcnow)
    
    # Mối quan hệ với bảng User
    user = relationship('User', back_populates='achievements')

class LearningProgress(Base):
    """
    Detailed tracking of user's learning progress
    """
    __tablename__ = 'learning_progress'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Learning session details
    session_date = Column(DateTime, default=datetime.utcnow)
    study_duration = Column(Float, default=0.0)  # in minutes
    words_learned = Column(Integer, default=0)
    words_reviewed = Column(Integer, default=0)
    
    # Learning context
    topic = Column(String(100), nullable=True)
    difficulty_level = Column(String(50), nullable=True)
    
    # Performance metrics
    accuracy_rate = Column(Float, default=0.0)
    
    # Relationship with User
    user = relationship('User', back_populates='learning_progress')

class UserModel:
    def __init__(self, db_path='../flashcards.db'):
        self.db_path = db_path
        
        # Tạo engine và session
        self.engine = create_engine(f'sqlite:///{self.db_path}', echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        
        # Tạo bảng nếu chưa tồn tại
        Base.metadata.create_all(bind=self.engine)
    
    def _get_connection(self):
        """Tạo session database"""
        return self.SessionLocal()
    
    def _hash_password(self, password, salt=None):
        """Tạo hash mật khẩu an toàn"""
        if salt is None:
            salt = uuid.uuid4().hex
        
        # Sử dụng SHA-256 để hash mật khẩu
        hashed_password = hashlib.sha256((salt + password).encode()).hexdigest()
        return salt, hashed_password
    
    def validate_email(self, email):
        """Kiểm tra định dạng email"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None
    
    def validate_password_strength(self, password):
        """
        Kiểm tra độ mạnh mật khẩu:
        - Ít nhất 8 ký tự
        - Chứa chữ hoa và chữ thường
        - Chứa ít nhất một số
        - Chứa ít nhất một ký tự đặc biệt
        """
        if len(password) < 8:
            return False
        
        # Kiểm tra chữ hoa, chữ thường, số và ký tự đặc biệt
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        return has_upper and has_lower and has_digit and has_special
    
    def create_user(self, username, email, password):
        """Tạo người dùng mới"""
        if not self.validate_email(email):
            raise ValueError("Email không hợp lệ")
        
        if not self.validate_password_strength(password):
            raise ValueError("Mật khẩu không đủ mạnh")
        
        salt, hashed_password = self._hash_password(password)
        
        session = self._get_connection()
        try:
            # Kiểm tra xem username hoặc email đã tồn tại chưa
            existing_user = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                raise ValueError("Username hoặc email đã được sử dụng")
            
            # Tạo người dùng mới
            new_user = User(
                username=username,
                email=email,
                password_salt=salt,
                password_hash=hashed_password,
                language_level='Beginner',
                learning_goal='Cải thiện từ vựng tiếng Anh'
            )
            
            session.add(new_user)
            session.commit()
            return new_user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def authenticate_user(self, username, password):
        """Xác thực người dùng"""
        session = self._get_connection()
        try:
            user = session.query(User).filter(User.username == username).first()
            
            if not user:
                return None
            
            # Kiểm tra mật khẩu
            _, hashed_input = self._hash_password(password, user.password_salt)
            
            if hashed_input == user.password_hash:
                return user
            
            return None
        finally:
            session.close()

def main():
    user_model = UserModel()
    
    # Example usage
    try:
        # Register a new user with more details
        user_id = user_model.create_user(
            'johndoe', 
            'john@example.com', 
            'SecurePass123!', 
        )
        print(f"User registered with ID: {user_id.id}")
        
        # Authenticate user
        authenticated_user = user_model.authenticate_user('johndoe', 'SecurePass123!')
        if authenticated_user:
            print("User authenticated successfully")
        else:
            print("Authentication failed")
        
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
