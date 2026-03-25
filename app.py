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

# Setup Logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_object(Config)

# Fix URL Database & Secret Key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tammam_asta_super_secret_2026')
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri or app.config.get('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Inisialisasi Database (Pastikan db.drop_all() hanya aktif jika ingin reset total)
with app.app_context():
    try:
        # db.drop_all() # Aktifkan hanya jika ada error kolom tidak ditemukan
        db.create_all()
        logging.info("Database synchronized.")
    except Exception as e:
        logging.error(f"DB Error: {e}")

app.register_blueprint(admin_bp, url_prefix='/admin')

# ======================
# HALAMAN INDEX (Informasi Only)
# ======================
@app.route('/')
def index():
    return render_template('index.html')

# Action untuk membuat user otomatis dan mulai survei
@app.route('/mulai', methods=['POST'])
def mulai_survei():
    try:
        # Membuat user anonim agar sistem tetap bisa menyimpan relasi data
        new_user = User(nama="Pengguna Baru", tipe_user='Siswa')
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('input_bobot', user_id=new_user.user_id))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error Create User: {e}")
        return "Gagal memulai sistem. Pastikan database sudah terhubung.", 500

# ======================
# 1. INPUT BOBOT
# ======================
@app.route('/bobot/<int:user_id>', methods=['GET', 'POST'])
def input_bobot(user_id):
    user = User.query.get_or_404(user_id)
    kriteria_list = Kriteria.query.all()

    if not kriteria_list:
        return "Error: Data Kriteria masih kosong.", 500

    if request.method == 'POST':
        try:
            # --- BAGIAN PERBAIKAN NAMA ---
            nama_input = request.form.get('nama', '').strip()
            if nama_input:
                user.nama = nama_input  # Update nama "Pengguna Baru" menjadi nama asli
            # -----------------------------

            # Hapus data bobot lama jika ada
            BobotKriteria.query.filter_by(user_id=user_id).delete()
            
            for k in kriteria_list:
                val = request.form.get(f'bobot_{k.kriteria_id}', 0)
                db.session.add(BobotKriteria(
                    user_id=user_id, 
                    kriteria_id=k.kriteria_id, 
                    bobot_input=float(val)
                ))
            
            db.session.commit() # Nama dan Bobot tersimpan permanen
            return redirect(url_for('input_survey', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error Simpan Bobot: {e}")
            return f"Error: {e}", 500

    return render_template('input_bobot.html', kriteria=kriteria_list, user=user)

# ======================
# 2. INPUT SURVEY & MOORA
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan_list = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()
    prodis = ProgramStudi.query.limit(3).all()

    if not pertanyaan_list or len(prodis) < 3:
        return "Data pendukung (Pertanyaan/Prodi) belum lengkap di database.", 500

    if request.method == 'POST':
        try:
            SurveyJawaban.query.filter_by(user_id=user_id).delete()
            PenilaianAlternatif.query.filter_by(user_id=user_id).delete()
            
            mapping = {'A': [5, 3, 2], 'B': [2, 5, 3], 'C': [1, 2, 5]}

            for p in pertanyaan_list:
                jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
                if jawaban:
                    db.session.add(SurveyJawaban(user_id=user_id, pertanyaan_id=p.pertanyaan_id, jawaban=jawaban))
                    nilai_list = mapping.get(jawaban.upper(), [0, 0, 0])
                    for idx, prd in enumerate(prodis):
                        db.session.add(PenilaianAlternatif(
                            user_id=user_id, prodi_id=prd.prodi_id,
                            kriteria_id=p.kriteria_id, nilai=float(nilai_list[idx])
                        ))
            db.session.commit()
            return redirect(url_for('hitung_moora', user_id=user_id))
        except Exception as e:
            db.session.rollback()
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
        flash("Data tidak lengkap.", "warning")
        return redirect(url_for('index'))

    total_bobot = sum(b.bobot_input for b in bobot_user) or 1
    b_norm = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_user}

    try:
        HasilKeputusan.query.filter_by(user_id=user_id).delete()
        hasil_display = []

        for p in prodi_list:
            skor = 0
            for k in kriteria_list:
                nilai_obj = next((pn for pn in penilaian_user if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
                nilai = nilai_obj.nilai if nilai_obj else 0
                skor += b_norm.get(k.kriteria_id, 0) * nilai
            
            db.session.add(HasilKeputusan(user_id=user_id, prodi_id=p.prodi_id, skor_akhir=skor))
            hasil_display.append({
                'nama_prodi': p.nama_prodi, 
                'skor_akhir': round(skor, 4), 
                'deskripsi': p.deskripsi or "Belum ada deskripsi."
            })

        db.session.commit()
        hasil_display = sorted(hasil_display, key=lambda x: x['skor_akhir'], reverse=True)
        return render_template('hasil.html', user=user, hasil=hasil_display)
    except Exception as e:
        db.session.rollback()
        return f"Error: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)