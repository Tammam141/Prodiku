import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from config import Config
from models import (
    db, User, Kriteria, ProgramStudi,
    BobotKriteria, PenilaianAlternatif, HasilKeputusan,
    PertanyaanSurvei, SurveyJawaban
)
from admin_routes import admin_bp

# Setup Logging agar error muncul di Vercel/Hosting Logs
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(Config)

# 1. FIX URL DATABASE & SECRET KEY
# Penting: PostgreSQL di hosting sering menggunakan awalan 'postgres://' 
# yang harus diubah menjadi 'postgresql://' agar dikenali SQLAlchemy terbaru.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_asta_super_secret_2026')
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or app.config.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# 2. OTOMATISASI DATABASE (Sangat Penting untuk Hosting)
# Memastikan tabel dibuat otomatis saat aplikasi dijalankan.
with app.app_context():
    try:
        # Jika Anda sering mengalami UndefinedColumn, aktifkan db.drop_all() 
        # satu kali saja untuk mereset skema, lalu beri komentar lagi.
        # db.drop_all() 
        db.create_all()
        logging.info("Database synchronized successfully.")
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

# Registrasi Blueprint Admin
app.register_blueprint(admin_bp, url_prefix='/admin')

# ======================
# HALAMAN INDEX
# ======================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        if not nama:
            flash("Nama tidak boleh kosong!", "danger")
            return redirect(url_for('index'))
        
        try:
            # Gunakan 'user' atau 'users' sesuai definisi di models.py
            new_user = User(nama=nama, tipe_user='Siswa')
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('input_bobot', user_id=new_user.user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error Index: {e}")
            return f"Error Simpan User: {e}", 500
            
    return render_template('index.html')

# ======================
# 1. INPUT BOBOT
# ======================
@app.route('/bobot/<int:user_id>', methods=['GET', 'POST'])
def input_bobot(user_id):
    user = User.query.get_or_404(user_id)
    kriteria_list = Kriteria.query.all()

    if not kriteria_list:
        return "Error: Data Kriteria belum diisi oleh Admin di Database.", 500

    if request.method == 'POST':
        try:
            # Hapus bobot lama user jika ada sebelum update
            BobotKriteria.query.filter_by(user_id=user_id).delete()
            
            for k in kriteria_list:
                val = request.form.get(f'bobot_{k.kriteria_id}', 0)
                db.session.add(BobotKriteria(
                    user_id=user_id, 
                    kriteria_id=k.kriteria_id, 
                    bobot_input=float(val)
                ))
            db.session.commit()
            return redirect(url_for('input_survey', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error Bobot: {e}")
            return f"Error Simpan Bobot: {e}", 500

    return render_template('input_bobot.html', kriteria=kriteria_list, user=user)

# ======================
# 2. INPUT SURVEY
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan_list = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()

    if not pertanyaan_list:
        return "Error: Tabel pertanyaan_survei kosong. Isi melalui Dashboard Admin.", 500

    if request.method == 'POST':
        try:
            # Bersihkan data lama user untuk rute ini
            SurveyJawaban.query.filter_by(user_id=user_id).delete()
            PenilaianAlternatif.query.filter_by(user_id=user_id).delete()
            
            mapping = {'A': [5, 3, 2], 'B': [2, 5, 3], 'C': [1, 2, 5]}
            prodis = ProgramStudi.query.limit(3).all()

            if len(prodis) < 3:
                return "Error: Dibutuhkan minimal 3 Program Studi di database.", 400

            for p in pertanyaan_list:
                jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
                if jawaban:
                    # Simpan Jawaban
                    db.session.add(SurveyJawaban(
                        user_id=user_id, 
                        pertanyaan_id=p.pertanyaan_id, 
                        jawaban=jawaban
                    ))
                    
                    # Simpan Penilaian Moora (mapping jawaban ke nilai numerik)
                    nilai_list = mapping.get(jawaban.upper(), [0, 0, 0])
                    for idx, prd in enumerate(prodis):
                        db.session.add(PenilaianAlternatif(
                            user_id=user_id, 
                            prodi_id=prd.prodi_id,
                            kriteria_id=p.kriteria_id, 
                            nilai=float(nilai_list[idx])
                        ))
            db.session.commit()
            return redirect(url_for('hitung_moora', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error Survey: {e}")
            return f"Error Simpan Survey: {e}", 500

    return render_template('input_survey.html', user=user, pertanyaan=pertanyaan_list)

# ======================
# 3. HASIL MOORA
# ======================
@app.route('/hasil/<int:user_id>')
def hitung_moora(user_id):
    user = User.query.get_or_404(user_id)
    prodi_list = ProgramStudi.query.all()
    kriteria_list = Kriteria.query.all()
    bobot_user = BobotKriteria.query.filter_by(user_id=user_id).all()
    penilaian_user = PenilaianAlternatif.query.filter_by(user_id=user_id).all()

    if not bobot_user or not penilaian_user:
        flash("Data belum lengkap untuk melakukan perhitungan.", "warning")
        return redirect(url_for('index'))

    # Perhitungan MOORA sederhana (Weighted Sum Model)
    total_bobot = sum(b.bobot_input for b in bobot_user) or 1
    b_norm = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_user}

    try:
        # Hapus hasil lama user
        HasilKeputusan.query.filter_by(user_id=user_id).delete()
        hasil_display = []

        for p in prodi_list:
            skor = 0
            for k in kriteria_list:
                # Cari nilai alternatif untuk prodi dan kriteria ini
                nilai_obj = next((pn for pn in penilaian_user if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
                nilai = nilai_obj.nilai if nilai_obj else 0
                skor += b_norm.get(k.kriteria_id, 0) * nilai
            
            # Simpan hasil ke DB
            db.session.add(HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor))
            hasil_display.append({
                'nama_prodi': p.nama_prodi, 
                'skor_akhir': round(skor, 4), 
                'deskripsi': p.deskripsi or "Belum ada deskripsi."
            })

        db.session.commit()
        # Urutkan berdasarkan skor tertinggi
        hasil_display = sorted(hasil_display, key=lambda x: x['skor_akhir'], reverse=True)
        return render_template('hasil.html', user=user, hasil=hasil_display)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error Moora: {e}")
        return f"Error Perhitungan: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)