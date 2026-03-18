# admin_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from functools import wraps
from models import db, Kriteria, ProgramStudi, PertanyaanSurvei, User, HasilKeputusan

# Membuat Blueprint untuk admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates/admin')

# =======================================================
# 1. DECORATOR UNTUK MELINDUNGI HALAMAN ADMIN
# =======================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Anda harus login untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# =======================================================
# 2. ROUTE UNTUK LOGIN DAN LOGOUT
# =======================================================
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Cek username dan password dengan yang ada di config
        if username == current_app.config['ADMIN_USERNAME'] and password == current_app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Username atau Password salah.', 'danger')
            return redirect(url_for('admin.login'))
            
    # Jika sudah login, langsung arahkan ke dashboard
    if 'admin_logged_in' in session:
        return redirect(url_for('admin.dashboard'))

    return render_template('login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

# =======================================================
# 3. DASHBOARD & MANAJEMEN DATA
# =======================================================

@admin_bp.route('/')
@login_required
def dashboard():
    users_count = User.query.count()
    kriteria_count = Kriteria.query.count()
    prodi_count = ProgramStudi.query.count()
    pertanyaan_count = PertanyaanSurvei.query.count()
    return render_template(
        'dashboard.html',
        users_count=users_count,
        kriteria_count=kriteria_count,
        prodi_count=prodi_count,
        pertanyaan_count=pertanyaan_count
    )

# --- MANAJEMEN KRITERIA ---
@admin_bp.route('/kriteria')
@login_required
def manage_kriteria():
    kriteria = Kriteria.query.all()
    return render_template('manage_kriteria.html', kriteria=kriteria)

@admin_bp.route('/kriteria/add', methods=['POST'])
@login_required
def add_kriteria():
    kode = request.form.get('kode_kriteria')
    nama = request.form.get('nama_kriteria')
    penjelasan = request.form.get('penjelasan')
    if not kode or not nama:
        flash('Kode dan Nama Kriteria wajib diisi.', 'error')
    else:
        new_kriteria = Kriteria(kode_kriteria=kode, nama_kriteria=nama, penjelasan=penjelasan)
        db.session.add(new_kriteria)
        db.session.commit()
        flash('Kriteria baru berhasil ditambahkan.', 'success')
    return redirect(url_for('admin.manage_kriteria'))

@admin_bp.route('/kriteria/update/<int:id>', methods=['POST'])
@login_required
def update_kriteria(id):
    kriteria = Kriteria.query.get_or_404(id)
    kriteria.kode_kriteria = request.form.get('kode_kriteria')
    kriteria.nama_kriteria = request.form.get('nama_kriteria')
    kriteria.penjelasan = request.form.get('penjelasan')
    db.session.commit()
    flash('Kriteria berhasil diperbarui.', 'success')
    return redirect(url_for('admin.manage_kriteria'))

@admin_bp.route('/kriteria/delete/<int:id>')
@login_required
def delete_kriteria(id):
    kriteria_to_delete = Kriteria.query.get_or_404(id)
    db.session.delete(kriteria_to_delete)
    db.session.commit()
    flash('Kriteria telah dihapus.', 'success')
    return redirect(url_for('admin.manage_kriteria'))


# --- MANAJEMEN PROGRAM STUDI ---
@admin_bp.route('/prodi')
@login_required
def manage_prodi():
    prodi = ProgramStudi.query.all()
    return render_template('manage_prodi.html', prodi=prodi)

@admin_bp.route('/prodi/add', methods=['POST'])
@login_required
def add_prodi():
    nama = request.form.get('nama_prodi')
    deskripsi = request.form.get('deskripsi')
    if not nama:
        flash('Nama Program Studi wajib diisi.', 'error')
    else:
        new_prodi = ProgramStudi(nama_prodi=nama, deskripsi=deskripsi)
        db.session.add(new_prodi)
        db.session.commit()
        flash('Program Studi baru berhasil ditambahkan.', 'success')
    return redirect(url_for('admin.manage_prodi'))

@admin_bp.route('/prodi/update/<int:id>', methods=['POST'])
@login_required
def update_prodi(id):
    prodi = ProgramStudi.query.get_or_404(id)
    prodi.nama_prodi = request.form.get('nama_prodi')
    prodi.deskripsi = request.form.get('deskripsi')
    db.session.commit()
    flash('Program Studi berhasil diperbarui.', 'success')
    return redirect(url_for('admin.manage_prodi'))

@admin_bp.route('/prodi/delete/<int:id>')
@login_required
def delete_prodi(id):
    prodi_to_delete = ProgramStudi.query.get_or_404(id)
    db.session.delete(prodi_to_delete)
    db.session.commit()
    flash('Program Studi telah dihapus.', 'success')
    return redirect(url_for('admin.manage_prodi'))


# --- MANAJEMEN PERTANYAAN SURVEI ---
@admin_bp.route('/pertanyaan')
@login_required
def manage_pertanyaan():
    # PENTING: Tambahkan order_by agar urutan sama dengan halaman user
    pertanyaan_list = PertanyaanSurvei.query.order_by(PertanyaanSurvei.pertanyaan_id.asc()).all()
    kriteria_list = Kriteria.query.all()
    return render_template('manage_pertanyaan.html', pertanyaan=pertanyaan_list, kriteria_list=kriteria_list)

@admin_bp.route('/pertanyaan/add', methods=['POST'])
@login_required
def add_pertanyaan():
    kriteria_id = request.form.get('kriteria_id')
    pertanyaan_text = request.form.get('pertanyaan') # Ambil dari name="pertanyaan" di form
    opsi_a = request.form.get('opsi_a')
    opsi_b = request.form.get('opsi_b')
    opsi_c = request.form.get('opsi_c')
    
    if not all([kriteria_id, pertanyaan_text, opsi_a, opsi_b, opsi_c]):
        flash('Semua field pertanyaan wajib diisi.', 'error')
    else:
        # Sinkronisasi: Menggunakan 'teks_pertanyaan' sesuai model terbaru
        new_pertanyaan = PertanyaanSurvei(
            kriteria_id=kriteria_id, 
            teks_pertanyaan=pertanyaan_text, 
            opsi_a=opsi_a, 
            opsi_b=opsi_b, 
            opsi_c=opsi_c
        )
        db.session.add(new_pertanyaan)
        db.session.commit()
        flash('Pertanyaan survei berhasil ditambahkan.', 'success')
    return redirect(url_for('admin.manage_pertanyaan'))

@admin_bp.route('/pertanyaan/update/<int:id>', methods=['POST'])
@login_required
def update_pertanyaan(id):
    p = PertanyaanSurvei.query.get_or_404(id)
    p.kriteria_id = request.form.get('kriteria_id')
    # Sinkronisasi: Menggunakan 'teks_pertanyaan'
    p.teks_pertanyaan = request.form.get('pertanyaan')
    p.opsi_a = request.form.get('opsi_a')
    p.opsi_b = request.form.get('opsi_b')
    p.opsi_c = request.form.get('opsi_c')
    db.session.commit()
    flash('Pertanyaan survei berhasil diperbarui.', 'success')
    return redirect(url_for('admin.manage_pertanyaan'))

@admin_bp.route('/pertanyaan/delete/<int:id>')
@login_required
def delete_pertanyaan(id):
    p_to_delete = PertanyaanSurvei.query.get_or_404(id)
    db.session.delete(p_to_delete)
    db.session.commit()
    flash('Pertanyaan survei telah dihapus.', 'success')
    return redirect(url_for('admin.manage_pertanyaan'))


# --- MELIHAT HASIL PENGGUNA ---
@admin_bp.route('/hasil')
@login_required
def view_results():
    results = HasilKeputusan.query.order_by(HasilKeputusan.user_id, HasilKeputusan.skor_akhir.desc()).all()
    user_results = {}
    for hasil in results:
        if hasil.user_id not in user_results:
            user_results[hasil.user_id] = {
                'user_nama': hasil.user.nama,
                'keputusan': []
            }
        user_results[hasil.user_id]['keputusan'].append({
            'prodi_nama': hasil.prodi.nama_prodi,
            'skor_akhir': hasil.skor_akhir,
            'tanggal': hasil.tanggal_keputusan
        })
    return render_template('view_results.html', user_results=user_results)