import os

class Config:
    """
    Konfigurasi aplikasi Flask untuk menghubungkan ke database PostgreSQL.
    """
    
    # 1. Koneksi Database PostgreSQL
    # Format: postgresql://[user]:[password]@[host]:[port]/[nama_database]
    # Berdasarkan data Anda:
    # user: postgres, password: admin, host: 127.0.0.1, database: prodiku
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:admin@127.0.0.1:5432/prodiku'
    
    # Menghalangi overhead memori tambahan dari SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 2. Keamanan Session
    # Menggunakan os.urandom untuk menghasilkan key yang kuat
    # Catatan: Jika ingin session login tidak terhapus saat restart server,
    # ganti os.urandom(24) dengan string tetap, misal: 'kunci-rahasia-saya-123'
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)

    # 3. Kredensial Admin Dashboard
    # Digunakan untuk login ke halaman /admin
    ADMIN_USERNAME = 'postgres'
    ADMIN_PASSWORD = 'admin'

    # 4. Konfigurasi Tambahan (Opsional)
    # Menghindari sorting otomatis pada JSON agar response lebih konsisten
    JSON_SORT_KEYS = False