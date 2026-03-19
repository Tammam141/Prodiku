import os

class Config:
    # Ambil URL dari Environment Variable
    database_url = os.environ.get('DATABASE_URL')
    
    # Perbaikan Otomatis: Ganti postgres:// menjadi postgresql://
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Gunakan URL yang sudah diperbaiki atau fallback ke localhost
    SQLALCHEMY_DATABASE_URI = database_url or \
        'postgresql://postgres:admin@localhost:5432/prodiku'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-prodiku'
    
    # Login Admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'postgres'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'