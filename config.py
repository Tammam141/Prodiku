import os

class Config:
    # Vercel akan memberikan variabel DATABASE_URL atau POSTGRES_URL
    # Kita buat agar aplikasi fleksibel (bisa lokal, bisa hosting)
    SQLALCHEMY_DATABASE_URI = os.environ.get('POSTGRES_URL') or \
                              os.environ.get('DATABASE_URL') or \
                              'postgresql://postgres:admin@127.0.0.1:5432/prodiku'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-anda'
    
    # Gunakan Env Var untuk Admin agar lebih aman saat di hosting
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'postgres'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'