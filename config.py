import os

class Config:
    # Vercel Neon biasanya memberikan variabel DATABASE_URL
    # Kita buat fleksibel agar bisa jalan di lokal maupun online
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'postgresql://postgres:admin@localhost:5432/prodiku'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-anda'
    
    # Login Admin Dashboard
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'postgres'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'