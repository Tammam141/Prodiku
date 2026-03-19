import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from config import Config
from models import (
    db, User, Kriteria, ProgramStudi,
    BobotKriteria, PenilaianAlternatif, HasilKeputusan,
    PertanyaanSurvei, SurveyJawaban
)
from admin_routes import admin_bp

app = Flask(__name__)
app.config.from_object(Config)

# Secret Key & Database URL Auto-fix
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_secret_123')
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or app.config.get('SQLALCHEMY_DATABASE_URI')

db.init_app(app)
app.register_blueprint(admin_bp)

# ======================
# HALAMAN INDEX (Input Nama Pertama Kali)
# ======================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        if not nama:
            return redirect(url_for('index'))
        
        # Buat user di sini
        user = User(nama=nama, tipe_user='Siswa')
        db.session.add(user)
        db.session.commit()
        
        # Lempar ke bobot dengan membawa user_id
        return redirect(url_for('input_bobot', user_id=user.user_id))
    
    return render_template('index.html')

# ======================
# 1. INPUT BOBOT
# ======================
@app.route('/bobot/<int:user_id>', methods=['GET', 'POST'])
def input_bobot(user_id):
    user = User.query.get_or_404(user_id)
    kriteria = Kriteria.query.all()

    if request.method == 'POST':
        # Simpan/Update Bobot
        BobotKriteria.query.filter_by(user_id=user_id).delete()
        for k in kriteria:
            val = request.form.get(f'bobot_{k.kriteria_id}', 0)
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
# 2. INPUT SURVEY
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()

    if not pertanyaan:
        return "Gagal: Tabel pertanyaan_survei kosong di database!", 500

    if request.method == 'POST':
        try:
            # 1. Bersihkan data lama
            SurveyJawaban.query.filter_by(user_id=user_id).delete()
            PenilaianAlternatif.query.filter_by(user_id=user_id).delete()
            
            # Mapping nilai: A=Sangat Sesuai (5), B=Sesuai (3), C=Cukup (2)
            mapping = {'A': [5, 3, 2], 'B': [2, 5, 3], 'C': [1, 2, 5]}

            for p in pertanyaan:
                jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
                if jawaban:
                    # Simpan jawaban mentah
                    db.session.add(SurveyJawaban(user_id=user_id, pertanyaan_id=p.pertanyaan_id, jawaban=jawaban))
                    
                    nilai_list = mapping.get(jawaban.upper(), [0, 0, 0])
                    
                    # Ambil ID Prodi yang ada di database kamu
                    all_prodi = ProgramStudi.query.all()
                    if not all_prodi:
                        return "Gagal: Tabel program_studi kosong!", 500
                        
                    for idx, prd in enumerate(all_prodi[:3]): # Ambil maksimal 3 prodi pertama
                        # Pastikan kriteria_id valid (ambil dari pertanyaan atau default ke 1)
                        kid = p.kriteria_id if p.kriteria_id else 1
                        
                        penilaian = PenilaianAlternatif(
                            user_id=user_id,
                            prodi_id=prd.prodi_id,
                            kriteria_id=kid,
                            nilai=float(nilai_list[idx] if idx < len(nilai_list) else 0)
                        )
                        db.session.add(penilaian)
            
            db.session.commit()
            return redirect(url_for('hitung_moora', user_id=user_id))
            
        except Exception as e:
            db.session.rollback()
            # Ini akan memunculkan pesan error aslinya di layar browser kamu
            return f"Error Detail: {str(e)}", 500

    return render_template('input_survey.html', user=user, pertanyaan=pertanyaan)

# ======================
# 3. HASIL MOORA
# ======================
@app.route('/hasil/<int:user_id>')
def hitung_moora(user_id):
    user = User.query.get_or_404(user_id)
    kriteria = Kriteria.query.all()
    prodi = ProgramStudi.query.all()
    bobot_list = BobotKriteria.query.filter_by(user_id=user_id).all()
    penilaian_list = PenilaianAlternatif.query.filter_by(user_id=user_id).all()

    total_bobot = sum(b.bobot_input for b in bobot_list) or 1
    b_norm = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_list}

    HasilKeputusan.query.filter_by(user_id=user_id).delete()
    hasil_display = []

    for p in prodi:
        skor = 0
        for k in kriteria:
            nilai_obj = next((pn for pn in penilaian_list if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
            nilai = nilai_obj.nilai if nilai_obj else 0
            skor += b_norm.get(k.kriteria_id, 0) * nilai
        
        db.session.add(HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor))
        hasil_display.append({'nama_prodi': p.nama_prodi, 'skor_akhir': round(skor, 4), 'deskripsi': p.deskripsi})

    db.session.commit()
    hasil_display = sorted(hasil_display, key=lambda x: x['skor_akhir'], reverse=True)
    return render_template('hasil.html', user=user, hasil=hasil_display)

if __name__ == '__main__':
    app.run(debug=True)