# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from models import (
    db, User, Kriteria, ProgramStudi,
    BobotKriteria, PenilaianAlternatif, HasilKeputusan,
    PertanyaanSurvei, SurveyJawaban
)
from datetime import date
from admin_routes import admin_bp # <--- 1. IMPORT BLUEPRINT ADMIN

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# 2. DAFTARKAN BLUEPRINT ADMIN KE APLIKASI UTAMA
app.register_blueprint(admin_bp)

# ======================
# HALAMAN INDEX / HOME
# ======================
@app.route('/')
def index():
    return render_template('index.html')

# ======================
# 1. INPUT BOBOT KRITERIA DENGAN VALIDASI
# ======================
@app.route('/bobot', methods=['GET', 'POST'])
def input_bobot():
    kriteria = Kriteria.query.all()
    error = None
    nama = ''

    if request.method == 'POST':
        nama = request.form.get('nama', '').strip()
        tipe_user = 'siswa'

        if not nama:
            error = "Nama harus diisi."
            return render_template('input_bobot.html', kriteria=kriteria, error=error, nama=nama)

        # Cek jika ada bobot yang bernilai 0
        semua_bobot = request.form.getlist('bobot_kriteria')
        if any(float(b) == 0 for b in semua_bobot):
             error = "Semua bobot kriteria harus diisi dan tidak boleh 0."
             # Mengambil ulang nilai yang sudah diinput untuk ditampilkan kembali di form
             bobot_values = {f'bobot_{k.kriteria_id}': request.form.get(f'bobot_{k.kriteria_id}') for k in kriteria}
             return render_template('input_bobot.html', kriteria=kriteria, error=error, nama=nama, bobot_values=bobot_values)

        user = User(nama=nama, tipe_user=tipe_user)
        db.session.add(user)
        db.session.commit()

        for k in kriteria:
            bobot_val = float(request.form.get(f'bobot_{k.kriteria_id}', 0))
            bobot = BobotKriteria(user_id=user.user_id, kriteria_id=k.kriteria_id, bobot_input=bobot_val)
            db.session.add(bobot)
        db.session.commit()

        return redirect(url_for('input_survey', user_id=user.user_id))

    return render_template('input_bobot.html', kriteria=kriteria, error=error, nama=nama)

# ======================
# 2. INPUT SURVEY PREFERENSI
# ======================
@app.route('/survey/<int:user_id>', methods=['GET', 'POST'])
def input_survey(user_id):
    user = User.query.get_or_404(user_id)
    pertanyaan = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()
   
    if request.method == 'POST':
        # Simpan dulu semua jawaban survey
        for p in pertanyaan:
            jawaban = request.form.get(f'jawaban[{p.pertanyaan_id}]')
            if jawaban:
                jawaban_entry = SurveyJawaban(user_id=user_id, pertanyaan_id=p.pertanyaan_id, jawaban=jawaban)
                db.session.add(jawaban_entry)
        db.session.commit()

        # Hapus penilaian lama jika ada
        PenilaianAlternatif.query.filter_by(user_id=user_id).delete()

        mapping = {
            'A': [5, 3, 2],  # [TI, TMJ, TMD]
            'B': [2, 5, 3],
            'C': [1, 2, 5]
        }

        # Buat penilaian alternatif berdasarkan jawaban
        all_jawaban = SurveyJawaban.query.filter_by(user_id=user_id).all()
        jawaban_dict = {j.pertanyaan_id: j.jawaban for j in all_jawaban}

        for p in pertanyaan:
            jawaban_user = jawaban_dict.get(p.pertanyaan_id)
            if jawaban_user:
                nilai_list = mapping.get(jawaban_user.upper(), [0, 0, 0])
                for idx, prodi_id in enumerate([1, 2, 3]):  # 1=TI, 2=TMJ, 3=TMD
                    nilai = nilai_list[idx]
                    penilaian = PenilaianAlternatif(
                        user_id=user_id,
                        prodi_id=prodi_id,
                        kriteria_id=p.kriteria_id,
                        nilai=nilai
                    )
                    db.session.add(penilaian)
        db.session.commit()
        return redirect(url_for('hitung_moora', user_id=user.user_id))

    return render_template('input_survey.html', user=user, pertanyaan=pertanyaan)

# ======================
# 3. PERHITUNGAN MOORA
# ======================
@app.route('/hasil/<int:user_id>')
def hitung_moora(user_id):
    user = User.query.get_or_404(user_id)
    kriteria = Kriteria.query.all()
    prodi = ProgramStudi.query.all()
    bobot_list = BobotKriteria.query.filter_by(user_id=user.user_id).all()
    penilaian_list = PenilaianAlternatif.query.filter_by(user_id=user_id).all()

    total_bobot = sum(b.bobot_input for b in bobot_list)
    if total_bobot == 0:
        return "Error: Total bobot tidak boleh 0.", 400

    bobot_normalisasi = {b.kriteria_id: b.bobot_input / total_bobot for b in bobot_list}

    skor_prodi = {}
    for p in prodi:
        skor = 0
        for k in kriteria:
            # Cari nilai yang sesuai
            nilai_obj = next((pn for pn in penilaian_list if pn.prodi_id == p.prodi_id and pn.kriteria_id == k.kriteria_id), None)
            nilai = nilai_obj.nilai if nilai_obj else 0
            
            bobot = bobot_normalisasi.get(k.kriteria_id, 0)
            skor += bobot * nilai
        skor_prodi[p.prodi_id] = skor

    HasilKeputusan.query.filter_by(user_id=user.user_id).delete()
    db.session.commit()

    for pid, skor in skor_prodi.items():
        hasil = HasilKeputusan(user_id=user.user_id, prodi_id=pid, skor_akhir=skor, tanggal_keputusan=date.today())
        db.session.add(hasil)
    db.session.commit()

    hasil_sorted = HasilKeputusan.query.filter_by(user_id=user.user_id).order_by(HasilKeputusan.skor_akhir.desc()).all()
    
    # Menggabungkan hasil dengan nama prodi untuk template
    hasil_final = []
    for h in hasil_sorted:
        prodi_obj = ProgramStudi.query.get(h.prodi_id)
        hasil_final.append({
            'prodi_id': h.prodi_id,
            'nama_prodi': prodi_obj.nama_prodi,
            'deskripsi': prodi_obj.deskripsi,
            'skor_akhir': h.skor_akhir
        })

    return render_template('hasil.html', user=user, hasil=hasil_final)


# ======================
# 4. RUNNING APP
# ======================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)