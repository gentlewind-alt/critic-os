"""
Configuration management for Flask app
Load from environment variables or use defaults
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = True
    JSON_SORT_KEYS = False
    
    # Spotify API
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8000/callback')
    
    # AI Settings
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Model paths
    EMOTION_MODEL_PATH = r"C:\Users\samar\OneDrive\Desktop\prodSt\emotion_model"
    MISTRAL_MODEL_PATH = r"C:\Users\samar\OneDrive\Desktop\prodSt\mistral-4bit-local"


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable not set")
