import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app import app
from models import db

# --- Sesuaikan dengan konfigurasi Anda ---
USER = 'postgres'
PASSWORD = 'admin'  # Pastikan ini sama dengan password saat Anda menginstal PostgreSQL
HOST = '127.0.0.1'
PORT = '5432'
DB_NAME = 'prodiku'
# -----------------------------------------

print("Mulai proses setup database...")

try:
    # 1. Konek ke server PostgreSQL bawaan untuk membuat database baru
    conn = psycopg2.connect(user=USER, password=PASSWORD, host=HOST, port=PORT, dbname='postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Cek apakah database sudah ada
    cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{DB_NAME}'")
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute(f'CREATE DATABASE {DB_NAME}')
        print(f"✅ Sukses: Database '{DB_NAME}' berhasil dibuat di PostgreSQL!")
    else:
        print(f"⚠️ Info: Database '{DB_NAME}' sudah ada sebelumnya.")
        
    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Gagal membuat database. Error: {e}")
    print("Pastikan PostgreSQL sudah berjalan dan passwordnya benar ('admin').")

print("-" * 40)

# 2. Membuat tabel-tabel berdasarkan model Flask-SQLAlchemy
try:
    with app.app_context():
        db.create_all()
    print("✅ Sukses: Semua tabel berhasil di-generate ke dalam database!")
except Exception as e:
    print(f"❌ Gagal membuat tabel. Error: {e}")

print("Proses selesai. Anda sudah bisa menjalankan 'python app.py'")