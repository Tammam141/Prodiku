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

# Setup Logging agar error muncul di Vercel Logs
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(Config)

# 1. FIX URL DATABASE & SECRET KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_asta_super_secret_2026')
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or app.config.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# =========================================================
# 2. SISTEM AUTO-SYNC DATABASE (SOLUSI ERROR UNDEFINED COLUMN)
# =========================================================
with app.app_context():
    try:
        # HAPUS SEMUA TABEL LAMA
        db.drop_all() 
        # BUAT ULANG SEMUA TABEL DENGAN SKEMA TERBARU
        db.create_all()
        logging.info("Database Berhasil Direset ke Skema Terbaru.")
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
            # Menggunakan model User sesuai models.py (table: users)
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
        return "Error: Data Kriteria masih kosong. Admin harus mengisi data di /admin.", 500

    if request.method == 'POST':
        try:
            # Hapus data bobot lama untuk user ini jika ada
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
# 2. INPUT SURVEY & PENILAIAN MOORA
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan_list = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()
    prodis = ProgramStudi.query.limit(3).all() # Mengambil 3 alternatif utama

    if not pertanyaan_list:
        return "Error: Tabel pertanyaan_survei kosong di database.", 500
    if len(prodis) < 3:
        return "Error: Minimal dibutuhkan 3 Program Studi di database untuk perhitungan.", 500

    if request.method == 'POST':
        try:
            # Pembersihan data lama agar sinkron saat pengisian ulang
            SurveyJawaban.query.filter_by(user_id=user_id).delete()
            PenilaianAlternatif.query.filter_by(user_id=user_id).delete()
            
            # Mapping Nilai MOORA: A=Sangat Minat(5), B=Minat(3), C=Kurang(1)
            # Anda bisa menyesuaikan angka ini sesuai kebutuhan bobot internal
            mapping = {'A': [5, 3, 2], 'B': [2, 5, 3], 'C': [1, 2, 5]}

            for p in pertanyaan_list:
                jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
                if jawaban:
                    # Simpan Jawaban Mentah
                    db.session.add(SurveyJawaban(
                        user_id=user_id, 
                        pertanyaan_id=p.pertanyaan_id, 
                        jawaban=jawaban
                    ))
                    
                    # Simpan Nilai ke Tabel Penilaian Alternatif untuk MOORA
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
        flash("Data tidak ditemukan. Harap isi survey kembali.", "warning")
        return redirect(url_for('index'))

    # Normalisasi Bobot Input
    total_bobot_val = sum(b.bobot_input for b in bobot_user) or 1
    b_norm = {b.kriteria_id: b.bobot_input / total_bobot_val for b in bobot_user}

    try:
        # Reset hasil lama
        HasilKeputusan.query.filter_by(user_id=user_id).delete()
        hasil_display = []

        for p in prodi_list:
            skor_akhir = 0
            for k in kriteria_list:
                # Ambil nilai alternatif yang sudah di-mapping dari survey
                nilai_obj = next((pn for pn in penilaian_user if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
                nilai_val = nilai_obj.nilai if nilai_obj else 0
                
                # Perhitungan Skor: Bobot Normalisasi * Nilai Alternatif
                skor_akhir += b_norm.get(k.kriteria_id, 0) * nilai_val
            
            # Simpan hasil ke database
            db.session.add(HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor_akhir))
            
            hasil_display.append({
                'nama_prodi': p.nama_prodi, 
                'skor_akhir': round(skor_akhir, 4), 
                'deskripsi': p.deskripsi or "Belum ada deskripsi."
            })

        db.session.commit()
        # Sorting dari nilai tertinggi
        hasil_display = sorted(hasil_display, key=lambda x: x['skor_akhir'], reverse=True)
        return render_template('hasil.html', user=user, hasil=hasil_display)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error Moora Calculate: {e}")
        return f"Error Perhitungan: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)