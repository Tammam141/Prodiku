import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import date
from config import Config
from models import (
    db, User, Kriteria, ProgramStudi,
    BobotKriteria, PenilaianAlternatif, HasilKeputusan,
    PertanyaanSurvei, SurveyJawaban
)
from admin_routes import admin_bp

app = Flask(__name__)
app.config.from_object(Config)

# PENTING: Secret Key wajib ada untuk menyimpan data di Session (Nama User)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_super_secret_123')

# Pastikan SQLAlchemy menggunakan postgresql:// (bukan postgres://)
uri = os.environ.get('DATABASE_URL', app.config.get('SQLALCHEMY_DATABASE_URI'))
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri

db.init_app(app)
app.register_blueprint(admin_bp)

# ======================
# HALAMAN INDEX / HOME
# ======================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        if not nama:
            flash("Nama harus diisi!")
            return redirect(url_for('index'))
        
        # Simpan nama di session agar tidak hilang saat pindah halaman
        session['user_nama'] = nama
        return redirect(url_for('input_bobot'))
    
    return render_template('index.html')

# ======================
# 1. INPUT BOBOT KRITERIA
# ======================
@app.route('/bobot', methods=['GET', 'POST'])
def input_bobot():
    kriteria = Kriteria.query.all()
    nama = session.get('user_nama')

    if not nama:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Simpan User Baru
        user = User(nama=nama, tipe_user='Siswa')
        db.session.add(user)
        db.session.commit()
        
        # Simpan User ID ke session untuk langkah berikutnya
        session['user_id'] = user.user_id

        # Simpan Bobot
        for k in kriteria:
            val = request.form.get(f'bobot_{k.kriteria_id}', 0)
            bobot = BobotKriteria(
                user_id=user.user_id, 
                kriteria_id=k.kriteria_id, 
                bobot_input=float(val) if val else 0
            )
            db.session.add(bobot)
        
        db.session.commit()
        return redirect(url_for('input_survey', user_id=user.user_id))

    return render_template('input_bobot.html', kriteria=kriteria, nama=nama)

# ======================
# 2. INPUT SURVEY PREFERENSI
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()

    if request.method == 'POST':
        # Bersihkan jawaban lama jika ada (mencegah duplikat)
        SurveyJawaban.query.filter_by(user_id=user_id).delete()
        
        for p in pertanyaan:
            jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
            if jawaban:
                entry = SurveyJawaban(user_id=user_id, pertanyaan_id=p.pertanyaan_id, jawaban=jawaban)
                db.session.add(entry)
        db.session.commit()

        # Pemetaan Jawaban ke Nilai (Metode MOORA)
        mapping = {
            'A': [5, 3, 2], # [Prodi 1, Prodi 2, Prodi 3]
            'B': [2, 5, 3],
            'C': [1, 2, 5]
        }

        # Reset Penilaian Alternatif
        PenilaianAlternatif.query.filter_by(user_id=user_id).delete()

        all_jawaban = SurveyJawaban.query.filter_by(user_id=user_id).all()
        for j in all_jawaban:
            nilai_list = mapping.get(j.jawaban.upper(), [0, 0, 0])
            for idx, prodi_id in enumerate([1, 2, 3]): # Sesuaikan dengan ID Prodi di DB
                penilaian = PenilaianAlternatif(
                    user_id=user_id,
                    prodi_id=prodi_id,
                    kriteria_id=j.pertanyaan_id % 5 + 1, # Logika distribusi kriteria
                    nilai=nilai_list[idx]
                )
                db.session.add(penilaian)
        
        db.session.commit()
        return redirect(url_for('hitung_moora', user_id=user_id))

    return render_template('input_survey.html', user=user, pertanyaan=pertanyaan)

# ======================
# 3. PERHITUNGAN MOORA & HASIL
# ======================
@app.route('/hasil/<int:user_id>')
def hitung_moora(user_id):
    user = User.query.get_or_404(user_id)
    kriteria = Kriteria.query.all()
    prodi = ProgramStudi.query.all()
    bobot_list = BobotKriteria.query.filter_by(user_id=user_id).all()
    penilaian_list = PenilaianAlternatif.query.filter_by(user_id=user_id).all()

    total_bobot = sum(b.bobot_input for b in bobot_list)
    if total_bobot == 0: total_bobot = 1 # Mencegah pembagian nol

    # 1. Normalisasi Bobot
    b_norm = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_list}

    # 2. Hitung Skor Akhir per Prodi
    HasilKeputusan.query.filter_by(user_id=user_id).delete()
    
    skor_final = []
    for p in prodi:
        skor = 0
        for k in kriteria:
            nilai_obj = next((pn for pn in penilaian_list if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
            nilai = nilai_obj.nilai if nilai_obj else 0
            skor += b_norm.get(k.kriteria_id, 0) * nilai
        
        hasil = HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor)
        db.session.add(hasil)
        skor_final.append({'nama_prodi': p.nama_prodi, 'skor_akhir': skor, 'deskripsi': p.deskripsi})

    db.session.commit()
    
    # Urutkan berdasarkan skor tertinggi
    skor_final = sorted(skor_final, key=lambda x: x['skor_akhir'], reverse=True)

    return render_template('hasil.html', user=user, hasil=skor_final)

if __name__ == '__main__':
    app.run(debug=True)