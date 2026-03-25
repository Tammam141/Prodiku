from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users' 
    user_id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    tipe_user = db.Column(db.String(50), nullable=False, default='Siswa')

class ProgramStudi(db.Model):
    __tablename__ = 'program_studi'
    prodi_id = db.Column(db.Integer, primary_key=True)
    nama_prodi = db.Column(db.String(100), nullable=False)
    deskripsi = db.Column(db.Text)

class Kriteria(db.Model):
    __tablename__ = 'kriteria'
    kriteria_id = db.Column(db.Integer, primary_key=True)
    kode_kriteria = db.Column(db.String(10), nullable=False)
    nama_kriteria = db.Column(db.String(100), nullable=False)
    penjelasan = db.Column(db.Text)
    
    # Relasi ke Pertanyaan
    pertanyaan = db.relationship('PertanyaanSurvei', 
                                 backref='kriteria', 
                                 lazy=True, 
                                 cascade="all, delete-orphan")

class PertanyaanSurvei(db.Model):
    __tablename__ = 'pertanyaan_survei'
    pertanyaan_id = db.Column(db.Integer, primary_key=True)
    kriteria_id = db.Column(db.Integer, db.ForeignKey('kriteria.kriteria_id'), nullable=False)
    teks_pertanyaan = db.Column(db.Text, nullable=False) 
    opsi_a = db.Column(db.Text)
    opsi_b = db.Column(db.Text)
    opsi_c = db.Column(db.Text)

class SurveyJawaban(db.Model):
    __tablename__ = 'survey_jawaban'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    pertanyaan_id = db.Column(db.Integer, db.ForeignKey('pertanyaan_survei.pertanyaan_id'), nullable=False)
    jawaban = db.Column(db.String(10), nullable=False)
    tanggal_input = db.Column(db.Date, default=date.today)

class BobotKriteria(db.Model):
    __tablename__ = 'bobot_kriteria'
    bobot_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    kriteria_id = db.Column(db.Integer, db.ForeignKey('kriteria.kriteria_id'), nullable=False)
    bobot_input = db.Column(db.Float, nullable=False)
    bobot_normalisasi = db.Column(db.Float)
    tanggal_input = db.Column(db.Date, default=date.today)

class PenilaianAlternatif(db.Model):
    __tablename__ = 'penilaian_alternatif'
    penilaian_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    prodi_id = db.Column(db.Integer, db.ForeignKey('program_studi.prodi_id'), nullable=False)
    kriteria_id = db.Column(db.Integer, db.ForeignKey('kriteria.kriteria_id'), nullable=False)
    nilai = db.Column(db.Float, nullable=False)

class HasilKeputusan(db.Model):
    __tablename__ = 'hasil_keputusan'
    keputusan_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    prodi_id = db.Column(db.Integer, db.ForeignKey('program_studi.prodi_id'), nullable=False)
    skor_akhir = db.Column(db.Float, nullable=False)
    tanggal_keputusan = db.Column(db.Date, default=date.today)
    
    # Menghubungkan relasi untuk mempermudah pemanggilan di template (hasil.html)
    user = db.relationship('User', backref='hasil')
    prodi = db.relationship('ProgramStudi', backref='hasil')