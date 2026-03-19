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

# Secret Key wajib untuk Session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_secret_key_999')

# Auto-fix postgres:// ke postgresql://
uri = os.environ.get('DATABASE_URL', app.config.get('SQLALCHEMY_DATABASE_URI'))
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri

db.init_app(app)
app.register_blueprint(admin_bp)

# ======================
# HALAMAN INDEX
# ======================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        if not nama:
            return redirect(url_for('index'))
        
        # Buat user baru agar ID-nya fresh
        user = User(nama=nama, tipe_user='Siswa')
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('input_bobot', user_id=user.user_id))
    
    return render_template('index.html')

# ======================
# 1. INPUT BOBOT KRITERIA
# ======================
@app.route('/bobot/<int:user_id>', methods=['GET', 'POST'])
def input_bobot(user_id):
    user = User.query.get_or_404(user_id)
    kriteria = Kriteria.query.all()

    if request.method == 'POST':
        # Bersihkan data lama user ini jika ada
        BobotKriteria.query.filter_by(user_id=user_id).delete()

        for k in kriteria:
            # Ambil nilai dari input name="bobot_{{ k.kriteria_id }}"
            val = request.form.get(f'bobot_{k.kriteria_id}')
            if val:
                bobot = BobotKriteria(
                    user_id=user_id, 
                    kriteria_id=k.kriteria_id, 
                    bobot_input=float(val)
                )
                db.session.add(bobot)
        
        db.session.commit()
        return redirect(url_for('input_survey', user_id=user_id))

    return render_template('input_bobot.html', kriteria=kriteria, user=user)

# ======================
# 2. INPUT SURVEY PREFERENSI
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()

    if request.method == 'POST':
        SurveyJawaban.query.filter_by(user_id=user_id).delete()
        PenilaianAlternatif.query.filter_by(user_id=user_id).delete()
        
        # Mapping skor MOORA: A=Sangat Sesuai, B=Sesuai, C=Kurang Sesuai
        mapping = {
            'A': [5, 3, 2], # Skor untuk [Prodi 1, Prodi 2, Prodi 3]
            'B': [2, 5, 3],
            'C': [1, 2, 5]
        }

        for p in pertanyaan:
            jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
            if jawaban:
                # 1. Simpan Jawaban Mentah
                entry = SurveyJawaban(user_id=user_id, pertanyaan_id=p.pertanyaan_id, jawaban=jawaban)
                db.session.add(entry)
                
                # 2. Konversi Jawaban ke Nilai Alternatif (WAJIB ADA UNTUK MOORA)
                nilai_list = mapping.get(jawaban.upper(), [0, 0, 0])
                for idx, prodi_id in enumerate([1, 2, 3]):
                    penilaian = PenilaianAlternatif(
                        user_id=user_id,
                        prodi_id=prodi_id,
                        kriteria_id=p.kriteria_id, # Pakai kriteria_id asli dari pertanyaan!
                        nilai=float(nilai_list[idx])
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

    # SAFETY CHECK: Jika data kurang, jangan lanjut hitung (biar gak error 500)
    if not bobot_list or not penilaian_list or not prodi:
        return f"Error: Data tidak lengkap. Bobot: {len(bobot_list)}, Penilaian: {len(penilaian_list)}, Prodi: {len(prodi)}"

    total_bobot = sum(b.bobot_input for b in bobot_list)
    if total_bobot == 0: total_bobot = 1

    b_norm = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_list}

    HasilKeputusan.query.filter_by(user_id=user_id).delete()
    
    hasil_display = []
    for p in prodi:
        skor = 0
        for k in kriteria:
            nilai_obj = next((pn for pn in penilaian_list if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
            # Jika nilai tidak ketemu, beri 0 daripada crash
            nilai = nilai_obj.nilai if nilai_obj else 0
            skor += b_norm.get(k.kriteria_id, 0) * nilai
        
        db.session.add(HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor))
        
        hasil_display.append({
            'nama_prodi': p.nama_prodi,
            'skor_akhir': round(skor, 4),
            'deskripsi': p.deskripsi or "Tidak ada deskripsi" # Tambahkan safety deskripsi
        })

    db.session.commit()
    hasil_display = sorted(hasil_display, key=lambda x: x['skor_akhir'], reverse=True)
    return render_template('hasil.html', user=user, hasil=hasil_display)

if __name__ == '__main__':
    app.run(debug=True)