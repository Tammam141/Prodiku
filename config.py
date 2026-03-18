import os

class Config:
    # Mengambil URL database online dari Vercel, jika tidak ada baru pakai lokal
    SQLALCHEMY_DATABASE_URI = os.environ.get('POSTGRES_URL') or \
                              'postgresql://postgres:admin@localhost:5432/prodiku'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-anda'
    
    # Data login admin
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'postgres'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'