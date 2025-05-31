import streamlit as st 
import pandas as pd 
import os 
import io 
import sqlite3 
from datetime import datetime
import pytz
from fpdf import FPDF 
import tempfile

os.environ['TZ'] = 'Asia/Jakarta'
try:
    import time
    time.tzset()
except:
    pass

def adapt_datetime(val): 
    return val.isoformat()

# Fungsi untuk mendapatkan waktu Indonesia
def get_indonesia_time():
    """Mendapatkan waktu sesuai timezone Indonesia (WIB)"""
    indonesia_tz = pytz.timezone('Asia/Jakarta')
    return datetime.now(indonesia_tz)

# Fungsi untuk format harga sesuai PUEBI
def format_harga(harga):
    """Format harga dengan format PUEBI: Rp1.000"""
    try:
        return f"Rp{int(harga):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp0"

# ---------- FUNGSI DATABASE ----------
def init_db():
    conn = sqlite3.connect('kasir.db')
    
    # Register adapter datetime
    sqlite3.register_adapter(datetime, adapt_datetime)
    
    c = conn.cursor()
    
    # Tabel users
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )
    ''')
    
    # Tabel produk
    c.execute('''
    CREATE TABLE IF NOT EXISTS produk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        harga INTEGER NOT NULL,
        stok INTEGER NOT NULL,
        gambar TEXT
    )
    ''')
    
    # Tabel riwayat transaksi
    c.execute('''
    CREATE TABLE IF NOT EXISTS riwayat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        harga INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        kasir TEXT NOT NULL,
        waktu TEXT NOT NULL,
        nota TEXT NOT NULL
    )
    ''')
    
    # Tabel nomor nota
    c.execute('''
    CREATE TABLE IF NOT EXISTS nomor_nota (
        tanggal TEXT PRIMARY KEY,
        nomor INTEGER NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

# ---------- FUNGSI PENGELOLAAN USER ----------
def load_users():
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    c.execute("SELECT username, password FROM users")
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result

def save_user(username, password):
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

# ---------- FUNGSI REGISTRASI ----------
def register():
    st.image("images/logokasir.png", width=100)
    st.title("Registrasi Akun Kasir")

    username = st.text_input("Username Baru")
    password = st.text_input("Password Baru", type="password")
    confirm_password = st.text_input("Konfirmasi Password", type="password")

    if st.button("Daftar"):
        if not username or not password or not confirm_password:
            st.error("Semua kolom harus diisi.")
        elif password != confirm_password:
            st.error("Password dan konfirmasi tidak cocok.")
        else:
            users = load_users()
            if username in users:
                st.error("Username sudah terdaftar.")
            else:
                save_user(username, password)
                st.success("Registrasi berhasil! Silakan login.")
                st.session_state.page = "login"
                st.rerun()

# ---------- FUNGSI LOGIN ----------
def login():
    st.image("images/logokasir.png", width=100)
    st.title("Login Kasir")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        users = load_users()
        if username in users and users[username] == password:
            st.success("Login berhasil!")
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Username atau password salah.")

    if st.button("Daftar Akun Baru"):
        st.session_state.page = "register"
        st.rerun()

# ---------- FUNGSI HALAMAN KASIR ----------
def get_nomor_nota():
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    # Menggunakan waktu Indonesia
    today = get_indonesia_time().strftime("%d%m%y")
    
    c.execute("SELECT nomor FROM nomor_nota WHERE tanggal = ?", (today,))
    result = c.fetchone()
    
    if result is None:
        nomor = 1
        c.execute("INSERT INTO nomor_nota (tanggal, nomor) VALUES (?, ?)", (today, nomor))
    else:
        nomor = result[0] + 1
        c.execute("UPDATE nomor_nota SET nomor = ? WHERE tanggal = ?", (nomor, today))
    
    conn.commit()
    conn.close()
    
    return f"CS/{today}/{str(nomor).zfill(4)}"

# ---------- FUNGSI KASIR ----------
def halaman_kasir():
    st.subheader("🛒 Kasir")
    
    init_db()
    
    # Ambil data produk
    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk WHERE stok > 0", conn)
    conn.close()

    if "keranjang" not in st.session_state:
        st.session_state.keranjang = []

    if not df.empty:
        for i, row in df.iterrows():
            col_img, col1, col2, col3 = st.columns([1.5, 3, 2, 1])
            with col_img:
                if pd.notna(row.get("gambar", None)) and os.path.exists(row["gambar"]):
                    st.image(row["gambar"], width=60)
                else:
                    st.empty()

            with col1:
                st.markdown(f"{row['nama']}")
                st.caption(f"{format_harga(row['harga'])} | Stok: {int(row['stok'])}")
   
            with col2:
                jumlah = st.number_input(f"Jumlah {row['nama']}", min_value=0, max_value=int(row["stok"]), key=f"jumlah_{i}")

            with col3:
                if st.button("Tambah", key=f"btn_{i}"):
                    if jumlah > 0:
                        st.session_state.keranjang.append((row["nama"], row["harga"], jumlah))
                        st.success(f"{row['nama']} ditambahkan!")
                        st.rerun()
    else:
        st.info("Belum ada produk tersedia atau stok habis.")

    if st.session_state.keranjang:
        st.write("### Keranjang Belanja")
        total = 0
        for i, (nama, harga, qty) in enumerate(st.session_state.keranjang):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{nama} x {qty} = {format_harga(harga * qty)}")
            with col2:
                if st.button("❌", key=f"remove_{i}", help="Hapus item"):
                    st.session_state.keranjang.pop(i)
                    st.rerun()
            total += harga * qty
        st.write(f"### Total: {format_harga(total)}")

        if st.button("🗑️ Kosongkan Keranjang"):
            st.session_state.keranjang = []
            st.rerun()

    if st.button("🧾 Cetak Struk") and st.session_state.keranjang:
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        stok_kurang = False

        # Periksa stok dalam transaksi
        for nama, harga, qty in st.session_state.keranjang:
            c.execute("SELECT stok FROM produk WHERE nama = ?", (nama,))
            result = c.fetchone()
            if result and result[0] >= qty:
                c.execute("UPDATE produk SET stok = stok - ? WHERE nama = ?", (qty, nama))
            else:
                st.error(f"Stok {nama} tidak cukup!")
                stok_kurang = True
                break

        if not stok_kurang:
            conn.commit()

            # Menggunakan waktu Indonesia
            now = get_indonesia_time()
            waktu_str = now.strftime("%d %b %y %H:%M")
            waktu_iso = now.isoformat()
            nomor_nota = get_nomor_nota()

            total = sum(harga * qty for _, harga, qty in st.session_state.keranjang)

            # struk
            struk_lines = []
            struk_lines.append("         Kasir Hijau")
            struk_lines.append("=" * 30)
            struk_lines.append(f"No Nota : {nomor_nota}")
            struk_lines.append(f"Waktu   : {waktu_str}")
            struk_lines.append("-" * 30)

            for nama, harga, qty in st.session_state.keranjang:
                total_item = harga * qty
                harga_formatted = f"Rp{total_item:,}".replace(",", ".")
                struk_lines.append(f"{qty} {nama:<18} {harga_formatted:>10}")

            struk_lines.append("-" * 30)
            subtotal_formatted = f"Rp{total:,}".replace(",", ".")
            struk_lines.append(f"Subtotal {len(st.session_state.keranjang)} Produk  {subtotal_formatted:>10}")
            total_formatted = f"Rp{total:,}".replace(",", ".")
            struk_lines.append(f"Total Tagihan        {total_formatted:>10}")
            struk_lines.append("")
            struk_lines.append("Kartu Debit/Kredit")
            bayar_formatted = f"Rp{total:,}".replace(",", ".")
            struk_lines.append(f"Total Bayar          {bayar_formatted:>10}")
            struk_lines.append("=" * 30)
            struk_lines.append(f"Terbayar {waktu_str}")
            struk_lines.append("Dicetak: Kasir")

            struk = "\n".join(struk_lines)
            st.text_area("🧾 Struk Transaksi", struk, height=300)
            st.download_button("📥 Unduh Struk TXT", data=struk, file_name=f"struk_{nomor_nota.replace('/', '_')}.txt", mime="text/plain")

            # MEMBUAT VERSI PDF
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Courier", size=10)
                for line in struk_lines:
                    pdf.cell(0, 10, txt=line, ln=1)

                pdf_bytes = pdf.output(dest="S").encode("latin-1")
                pdf_buffer = io.BytesIO(pdf_bytes)

                st.download_button("📄 Unduh Struk PDF", data=pdf_buffer, file_name=f"struk_{nomor_nota.replace('/', '_')}.pdf", mime="application/pdf")
            except Exception as e:
                st.warning("Gagal membuat PDF. Silakan gunakan versi TXT.")

            # SIMPAN RIWAYAT
            for nama, harga, qty in st.session_state.keranjang:
                c.execute("""
                    INSERT INTO riwayat (nama, harga, qty, kasir, waktu, nota)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nama, harga, qty, st.session_state.username, waktu_iso, nomor_nota))
            
            conn.commit()
            st.success("Pembelian berhasil!")
            st.session_state.keranjang = []
        
        conn.close()

# ----------- RESET DATA PRODUK -------------
def reset_data():
    if st.sidebar.button("🧹 Reset Data Produk"):
        if st.sidebar.button("⚠️ Konfirmasi Reset", type="secondary"):
            conn = sqlite3.connect('kasir.db')
            c = conn.cursor()
            c.execute("DELETE FROM produk")
            conn.commit()
            conn.close()
            st.success("Data produk berhasil direset!")
            st.rerun()

# ----------- FUNGSI TAMBAH PRODUK -------------   
def halaman_tambah_produk():
    st.title("Tambah Produk Baru")

    nama = st.text_input("Nama Produk")
    harga_str = st.text_input("Harga (contoh: 5000)")
    stok = st.number_input("Stok", min_value=0, step=1)
    gambar = st.file_uploader("Gambar Produk", type=["jpg", "jpeg", "png"])

    if st.button("Simpan"):
        if not nama or not harga_str:
            st.error("Nama produk dan harga harus diisi!")
            return

        try: 
            harga = int(harga_str.replace('.', '').replace(',', ''))
        except ValueError:
            st.error("Harga tidak valid. Harap isi angka seperti: 5000")
            return
        
        # SIMPAN GAMBAR
        gambar_path = ""
        if gambar:
            os.makedirs("images/produk", exist_ok=True)
            gambar_path = f"images/produk/{nama.replace(' ', '_')}.png"
            with open(gambar_path, "wb") as f:
                f.write(gambar.read())

        # SIMPAN KE DATABASE
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO produk (nama, harga, stok, gambar)
                VALUES (?, ?, ?, ?)
            """, (nama, harga, stok, gambar_path))
            conn.commit()
            st.success("Produk berhasil ditambahkan!")
        except sqlite3.IntegrityError:
            st.error("Gagal menambahkan produk. Periksa kembali data yang dimasukkan.")
        finally:
            conn.close()
    
# ---------- FUNGSI HAPUS PRODUK SATUAN ----------
def hapus_produk():
    st.subheader("🗑 Hapus Produk")

    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk", conn)
    conn.close()
    
    if df.empty:
        st.info("Tidak ada produk yang tersedia.")
        return
    
    produk_list = df["nama"].tolist()
    produk_dipilih = st.selectbox("Pilih produk yang ingin dihapus:", produk_list)

    if produk_dipilih and st.button("Hapus Produk"):
        if st.button("⚠️ Konfirmasi Hapus", type="secondary"):
            conn = sqlite3.connect('kasir.db')
            c = conn.cursor()
            c.execute("DELETE FROM produk WHERE nama = ?", (produk_dipilih,))
            conn.commit()
            conn.close()
            st.success(f"Produk '{produk_dipilih}' berhasil dihapus.")
            st.rerun()

# ---------- EDIT PRODUK -----------
def edit_produk():
    st.subheader("✏ Edit Produk")

    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk", conn)
    conn.close()
    
    if df.empty:
        st.info("Tidak ada produk untuk diedit.")
        return
    
    produk_list = df["nama"].tolist()
    produk_dipilih = st.selectbox("Pilih produk yang ingin diedit:", produk_list)

    if produk_dipilih:
        produk_row = df[df["nama"] == produk_dipilih].iloc[0]

        nama_baru = st.text_input("Nama Produk", value=produk_row["nama"])
        harga_str_baru = st.text_input("Harga (misal: 5000)", value=str(int(produk_row['harga'])))
        stok_baru = st.number_input("Stok", min_value=0, value=int(produk_row["stok"]))

        if st.button("Simpan Perubahan"):
            if not nama_baru or not harga_str_baru:
                st.error("Nama produk dan harga harus diisi!")
                return

            try:
                harga_baru = int(harga_str_baru.replace('.', '').replace(',', ''))
            except ValueError:
                st.error("Harga tidak valid. Harap isi angka seperti: 5000")
                return

            # UPDATE DATA
            conn = sqlite3.connect('kasir.db')
            c = conn.cursor()
            c.execute("""
                UPDATE produk 
                SET nama = ?, harga = ?, stok = ? 
                WHERE nama = ?
            """, (nama_baru, harga_baru, stok_baru, produk_dipilih))
            conn.commit()
            conn.close()

            st.success(f"Produk '{produk_dipilih}' berhasil diperbarui!")
            st.rerun()

# ---------- FUNGSI LAPORAN ----------
# Ganti fungsi halaman_laporan() yang ada dengan yang ini:

def halaman_laporan():
    st.subheader("📊 Laporan Produk")
    
    conn = sqlite3.connect('kasir.db')
    
    try:
        df = pd.read_sql_query("SELECT * FROM produk", conn)
        
        # Format harga untuk tampilan dataframe
        if not df.empty:
            df_display = df.copy()
            df_display['harga'] = df_display['harga'].apply(format_harga)
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("Belum ada produk yang tersedia.")

        st.subheader("🧾 Riwayat Transaksi")

        # Cek apakah ada riwayat transaksi
        c = conn.cursor()
        c.execute("SELECT count(*) FROM riwayat")
        count = c.fetchone()[0]
        
        if count == 0:
            st.info("Belum ada riwayat transaksi.")
            conn.close()
            return
        
        # Ambil data riwayat
        riwayat_df = pd.read_sql_query("SELECT * FROM riwayat ORDER BY waktu DESC", conn)
        
        # Parse waktu dengan lebih robust
        def parse_waktu_safe(waktu_str):
            try:
                if pd.isna(waktu_str) or waktu_str == '':
                    return pd.NaT
                    
                waktu_str = str(waktu_str)
                
                # Coba berbagai format
                if 'T' in waktu_str:
                    # Format ISO dengan timezone
                    if '+' in waktu_str or waktu_str.endswith('Z'):
                        dt = pd.to_datetime(waktu_str, errors='coerce', utc=True)
                        if not pd.isna(dt):
                            return dt.tz_convert('Asia/Jakarta')
                    else:
                        # Format ISO tanpa timezone
                        dt = pd.to_datetime(waktu_str, errors='coerce')
                        if not pd.isna(dt):
                            return dt.tz_localize('Asia/Jakarta')
                else:
                    # Format lain
                    dt = pd.to_datetime(waktu_str, errors='coerce')
                    if not pd.isna(dt):
                        return dt.tz_localize('Asia/Jakarta')
                        
                return pd.NaT
            except Exception:
                return pd.NaT
        
        # Konversi kolom waktu
        riwayat_df['waktu_parsed'] = riwayat_df['waktu'].apply(parse_waktu_safe)
        
        # Filter hanya data dengan waktu yang valid
        riwayat_df = riwayat_df[~pd.isna(riwayat_df['waktu_parsed'])]
        
        if riwayat_df.empty:
            st.warning("Tidak ada data transaksi dengan format waktu yang valid.")
            conn.close()
            return

        # PILIHAN FILTER
        filter_jenis = st.radio("Filter berdasarkan:", ["Semua", "Harian", "Mingguan", "Bulanan"], horizontal=True)

        filtered = riwayat_df.copy()

        if filter_jenis != "Semua":
            now = get_indonesia_time()
    
            if filter_jenis == "Harian":
                tanggal = st.date_input("Pilih Tanggal", now.date())
                filtered = riwayat_df[riwayat_df["waktu_parsed"].dt.date == tanggal]

            elif filter_jenis == "Mingguan":
                tahun = st.number_input("Tahun", value=now.year, step=1, min_value=2020, max_value=2030)
                minggu = st.selectbox("Pilih Minggu ke-", list(range(1, 54)), index=min(now.isocalendar()[1] - 1, 52))

                try:
                    filtered = riwayat_df[
                        (riwayat_df["waktu_parsed"].dt.isocalendar().week == minggu) &
                        (riwayat_df["waktu_parsed"].dt.year == tahun)
                    ]
                except Exception as e:
                    st.error(f"Error filter mingguan: {e}")
                    filtered = pd.DataFrame()

            elif filter_jenis == "Bulanan":
                bulan = st.selectbox("Pilih Bulan", 
                                    ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                                    "Juli", "Agustus", "September", "Oktober", "November", "Desember"], 
                                    index=now.month - 1)
                bulan_angka = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                                "Juli", "Agustus", "September", "Oktober", "November", "Desember"].index(bulan) + 1
                tahun = st.number_input("Tahun", value=now.year, step=1, min_value=2020, max_value=2030)
                    
                try:
                    filtered = riwayat_df[
                        (riwayat_df["waktu_parsed"].dt.month == bulan_angka) &
                        (riwayat_df["waktu_parsed"].dt.year == tahun)
                    ]
                except Exception as e:
                    st.error(f"Error filter bulanan: {e}")
                    filtered = pd.DataFrame()
        
        if filtered.empty:
            st.warning("Tidak ada transaksi untuk periode yang dipilih.")
        else:
            # Format untuk tampilan
            filtered_display = filtered.copy()
            filtered_display['harga'] = filtered_display['harga'].apply(format_harga)
            
            # Format waktu untuk tampilan
            try:
                filtered_display['waktu'] = filtered_display['waktu_parsed'].dt.strftime('%d/%m/%Y %H:%M')
            except Exception:
                filtered_display['waktu'] = filtered_display['waktu'].astype(str)
            
            # Hapus kolom waktu_parsed dari tampilan
            columns_order = ['id', 'nama', 'harga', 'qty', 'kasir', 'waktu', 'nota']
            filtered_display = filtered_display[columns_order]
            
            st.dataframe(filtered_display, use_container_width=True)

            # Hitung statistik
            try:
                total_transaksi = (filtered["harga"] * filtered["qty"]).sum()
                jumlah_item = filtered["qty"].sum()
                jumlah_nota = filtered["nota"].nunique()

                # TAMPILAN RINGKASAN
                st.markdown("### Ringkasan:")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Penjualan", format_harga(int(total_transaksi)))
                with col2:
                    st.metric("Total Item Terjual", f"{int(jumlah_item)} pcs")
                with col3:
                    st.metric("Jumlah Transaksi", f"{jumlah_nota} nota")

                # UNDUH SEBAGAI CSV
                csv_data = filtered_display.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Unduh Laporan CSV", csv_data, 
                                 f"laporan_transaksi_{filter_jenis.lower()}.csv", "text/csv")

                # Buat PDF
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(200, 10, txt="Laporan Riwayat Transaksi", ln=True, align="C")
                    pdf.ln(5)

                    # Tambahkan informasi periode
                    pdf.set_font("Arial", size=10)
                    if filter_jenis == "Harian":
                        pdf.cell(200, 8, txt=f"Periode: {tanggal}", ln=True, align="C")
                    elif filter_jenis == "Mingguan":
                        pdf.cell(200, 8, txt=f"Periode: Minggu ke-{minggu} Tahun {tahun}", ln=True, align="C")
                    elif filter_jenis == "Bulanan":
                        pdf.cell(200, 8, txt=f"Periode: {bulan} {tahun}", ln=True, align="C")
                    else:
                        pdf.cell(200, 8, txt="Periode: Semua Data", ln=True, align="C")

                    pdf.ln(5)

                    # Header tabel
                    pdf.set_font("Arial", "B", 8)
                    pdf.cell(15, 8, "ID", 1, 0, "C")
                    pdf.cell(40, 8, "Nama Produk", 1, 0, "C")
                    pdf.cell(25, 8, "Harga", 1, 0, "C")
                    pdf.cell(15, 8, "Qty", 1, 0, "C")
                    pdf.cell(25, 8, "Kasir", 1, 0, "C")
                    pdf.cell(35, 8, "Waktu", 1, 0, "C")
                    pdf.cell(35, 8, "No. Nota", 1, 1, "C")

                    # Isi tabel (batasi 50 baris)
                    pdf.set_font("Arial", size=7)
                    for index, row in filtered.head(50).iterrows():
                        harga_formatted = format_harga(row['harga'])
                    
                        # Format waktu
                        try:
                            waktu_formatted = row['waktu_parsed'].strftime("%d/%m/%y %H:%M")
                        except:
                            waktu_formatted = str(row['waktu'])[:16]
                    
                        # Potong text jika terlalu panjang
                        nama_produk = str(row['nama'])[:15] + "..." if len(str(row['nama'])) > 15 else str(row['nama'])
                        nomor_nota = str(row['nota'])[:20] + "..." if len(str(row['nota'])) > 20 else str(row['nota'])
                        kasir_name = str(row['kasir'])[:15] + "..." if len(str(row['kasir'])) > 15 else str(row['kasir'])
                        
                        pdf.cell(15, 6, str(row['id']), 1, 0, "C")
                        pdf.cell(40, 6, nama_produk, 1, 0, "L")
                        pdf.cell(25, 6, harga_formatted, 1, 0, "R")
                        pdf.cell(15, 6, str(int(row['qty'])), 1, 0, "C")
                        pdf.cell(25, 6, kasir_name, 1, 0, "L")
                        pdf.cell(35, 6, waktu_formatted, 1, 0, "C")
                        pdf.cell(35, 6, nomor_nota, 1, 1, "L")

                    # Tambahkan ringkasan
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(200, 8, "RINGKASAN:", ln=True)
                    pdf.set_font("Arial", size=9)
                    pdf.cell(200, 6, f"Total Penjualan: {format_harga(int(total_transaksi))}", ln=True)
                    pdf.cell(200, 6, f"Total Item Terjual: {int(jumlah_item)} pcs", ln=True)
                    pdf.cell(200, 6, f"Jumlah Transaksi: {jumlah_nota} nota", ln=True)

                    # Footer
                    pdf.ln(5)
                    pdf.set_font("Arial", "I", 8)
                    waktu_cetak = get_indonesia_time().strftime('%d %B %Y %H:%M:%S WIB')
                    pdf.cell(200, 6, f"Dicetak pada: {waktu_cetak}", ln=True, align="R")

                    # Output PDF
                    pdf_output = pdf.output(dest="S").encode("latin-1")
                    
                    st.download_button("📄 Unduh Laporan PDF", 
                                     pdf_output, 
                                     f"laporan_transaksi_{filter_jenis.lower()}.pdf", 
                                     "application/pdf")

                except Exception as e:
                    st.warning(f"Gagal membuat PDF: {str(e)}. Silakan gunakan versi CSV.")

            except Exception as e:
                st.error(f"Terjadi kesalahan dalam mengolah data laporan: {str(e)}")

    except Exception as e:
        st.error(f"Terjadi kesalahan saat mengakses database: {str(e)}")
    finally:
        conn.close()

# ---------- FUNGSI LOGOUT ----------   
def logout():
    if st.sidebar.button("🔒 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.page = "login"
        if 'keranjang' in st.session_state:
            del st.session_state.keranjang
        if 'menu' in st.session_state:
            del st.session_state.menu
        st.rerun()

# ---------- MAIN ----------
def main(): 
    # Set page config
    st.set_page_config(
        page_title="Kasir Hijau",
        page_icon="🛒",
        layout="wide"
    )
    
    init_db()
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False 
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.logged_in:
        # Sidebar
        with st.sidebar:
            try:
                st.image("images/logokasir.png", width=100)
            except:
                st.write("🛒 **Kasir Hijau**")
            
            st.markdown(f"### Halo, {st.session_state.username}")
            st.markdown("---")

            menu_options = {
                "Kasir": "🛒 Kasir",
                "Tambah Produk": "➕ Tambah Produk",
                "Edit Produk": "✏ Edit Produk",
                "Hapus Produk": "🗑 Hapus Produk",
                "Laporan": "📊 Laporan"
            }

            if 'menu' not in st.session_state:
                st.session_state.menu = "Kasir"

            for key, label in menu_options.items():
                if st.button(label, use_container_width=True):
                    st.session_state.menu = key
                    st.rerun()
            
            st.markdown("---")
            
            # Panggil fungsi logout dan reset_data
            logout()
            reset_data()

        # Main content
        if st.session_state.menu == "Kasir":
            halaman_kasir()
        elif st.session_state.menu == "Tambah Produk":
            halaman_tambah_produk()
        elif st.session_state.menu == "Edit Produk":
            edit_produk()
        elif st.session_state.menu == "Hapus Produk":
            hapus_produk()
        elif st.session_state.menu == "Laporan":
            halaman_laporan()

    else:
        # Login/Register pages
        if st.session_state.page == "login":
            login()
        elif st.session_state.page == "register":
            register()

if __name__ == "__main__":
    main()