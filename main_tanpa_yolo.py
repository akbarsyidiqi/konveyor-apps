import cv2
import numpy as np
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol
import streamlit as st
import time
import sqlite3
import pandas as pd

# ==========================================
# 1. INISIALISASI DATABASE (SQLite)
# ==========================================

def init_db():
    conn = sqlite3.connect("logistik_gudang.db")
    cursor = conn.cursor()
    # Tabel untuk menyimpan nomor resi secara unik
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scanned_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode_data TEXT UNIQUE,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_barcode_to_db(barcode_data):
    try:
        conn = sqlite3.connect("logistik_gudang.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scanned_packages (barcode_data) VALUES (?)", (barcode_data,))
        conn.commit()
        conn.close()
        return True  # Berhasil simpan data baru
    except sqlite3.IntegrityError:
        conn.close()
        return False  # Data sudah pernah ada (duplicate), diabaikan

def get_total_packages():
    conn = sqlite3.connect("logistik_gudang.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM scanned_packages")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def reset_db():
    conn = sqlite3.connect("logistik_gudang.db")
    cursor = conn.cursor()
    # Menghapus seluruh isi tabel tanpa menghapus struktur tabelnya
    cursor.execute("DELETE FROM scanned_packages")
    conn.commit()
    conn.close()

# Jalankan inisialisasi DB saat aplikasi pertama kali dimuat
init_db()

# ==========================================
# 2. ANTARMUKA UTAMA (Streamlit UI)
# ==========================================
st.set_page_config(page_title="Smart Conveyor Scanner", layout="wide")

st.title("📦 Smart Conveyor Barcode Scanner System")
st.write("Sistem Pemindaian Paket Otomatis Berbasis Computer Vision (ROI + PyZbar + SQLite)")

# Layout Kolom Dashboard
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📹 Live Camera Feed & Scanner")
    
    sumber_video = st.radio("Pilih Sumber Video:", ("Video Demo di Repo (MP4)", "Kamera HP (URL Stream)"))
    
    url_kamera_hp = ""
    if sumber_video == "Kamera HP (URL Stream)":
        # Dummy IP
        url_kamera_hp = st.text_input(
            "🔗 Masukkan URL Video dari HP:", 
            value="http://192.168.1.5:8080/video" 
        )
        st.caption("Gunakan aplikasi seperti 'IP Webcam' di Android.")
    
    # Petunjuk UX agar user tahu urutan penggunaannya
    st.info("💡 SOP: Matikan centang (uncheck) di bawah ini terlebih dahulu sebelum mengganti sumber video/URL.")
    
    run_scanner = st.checkbox("Nyalakan Scanner", value=False)
    frame_window = st.image([], width='stretch')

with col2:
    st.subheader("📊 Statistik & Kontrol Data")
    
    # Indikator Total Paket Real-time dari Database
    total_placeholder = st.empty()
    total_placeholder.metric(label="Total Paket di Database", value=get_total_packages())
    
    # Placeholder untuk FPS tulisan kecil
    fps_small_display = st.empty() 
    
    st.markdown("---")
    st.write("🔧 **Menu Administrasi Data**")
    
    # Tombol Reset
    if st.button("🔴 Kosongkan Semua Data (Reset)", type="primary", width='stretch'):
        reset_db()
        st.success("Database berhasil dikosongkan!")
        time.sleep(1)
        st.rerun() # Refresh halaman agar angka total paket langsung berubah jadi 0
    
    # Fungsi Ambil Data untuk CSV Export
    def fetch_data_for_csv():
        conn = sqlite3.connect("logistik_gudang.db")
        df = pd.read_sql_query("""
            SELECT id AS 'No', 
                barcode_data AS 'Nomor Resi', 
                scanned_at AS 'Waktu Pemindaian' 
            FROM scanned_packages 
            ORDER BY scanned_at DESC
        """, conn)
        conn.close()
        return df

    # Fitur Export to CSV
    df_current = fetch_data_for_csv()
    csv_data = df_current.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Export Data ke CSV (Excel)",
        data=csv_data,
        file_name=f"laporan_resi_gudang_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="download-csv",
        width='stretch'
    )
    st.markdown("---")
    st.write("📋 **Daftar Resi Terscan (Real-Time)**")
    
    # Buat wadah kosong untuk tabel
    table_placeholder = st.empty()
    
    # Isi wadah tersebut dengan data awal saat aplikasi baru dibuka
    df_current = fetch_data_for_csv()
    table_placeholder.dataframe(df_current, width='stretch', hide_index=True)
    
    st.write("🔍 **Kotak Intip Scanner (Otsu ROI)**")
    debug_image_window = st.image([], width='stretch')

# ==========================================
# 3. CORE PROCESSING LOOP (OpenCV + ROI + PyZbar)
# ==========================================

# Kamera HANYA diinisialisasi jika checkbox menyala
if run_scanner:
    if sumber_video == "Kamera HP (URL Stream)":
        video_source = url_kamera_hp
    else:
        video_source = "video-resi-jarak-30cm-terbaca-semua.mp4"

    cap = cv2.VideoCapture(video_source)

    # 💾 BUFFER MEMORI: Menyimpan resi yang sudah sukses dipindai di sesi ini
    if 'resi_terscan_cache' not in st.session_state:
        st.session_state.resi_terscan_cache = set()

    # Sapu bersih "cache visual"
    debug_image_window.empty()

    # Tentukan ukuran area pemindaian (Region of Interest / ROI)
    # Sesuaikan angka rasio ini dengan posisi paket di konveyor pada videomu
    # DISET FULL FRAME (100% Layar)
    ROI_X_RATIO, ROI_Y_RATIO = 0.0, 0.0  # Mulai dari ujung kiri (0%) dan atas (0%)
    ROI_W_RATIO, ROI_H_RATIO = 1.0, 1.0  # Lebar 100%, Tinggi 100%

    simbol_logistik = [
        ZBarSymbol.CODE128, ZBarSymbol.CODE39, ZBarSymbol.EAN13, 
        ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.QRCODE
    ]

    while cap.isOpened():
        start_time = time.time() # Catat waktu mulai
        ret, frame = cap.read()
        
        if not ret:
            break

        # Perkecil resolusi frame agar lebih ringan (opsional jika terasa lag)
        frame = cv2.resize(frame, (800, 600))

        # Simulasi delay untuk video rekaman agar tidak terlalu cepat (opsional)
        if sumber_video == "Video Demo di Repo (MP4)":
            time.sleep(0.02) 

        h, w, _ = frame.shape
        
        # 1. Definisikan Kotak ROI berdasarkan persentase resolusi layar
        x1 = int(w * ROI_X_RATIO)
        y1 = int(h * ROI_Y_RATIO)
        x2 = int(w * (ROI_X_RATIO + ROI_W_RATIO))
        y2 = int(h * (ROI_Y_RATIO + ROI_H_RATIO))

        # Gambar kotak ROI di frame utama (panduan operator)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(frame, "ZONA PINDAI BARCODE", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 2. Potong frame (Crop) HANYA pada area kotak ROI
        roi_frame = frame[y1:y2, x1:x2]

        # 3. Preprocessing Gambar untuk ROI (Grayscale -> Blur -> Otsu)
        gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        blurred_roi = cv2.GaussianBlur(gray_roi, (5, 5), 0)
        _, thresholded_roi = cv2.threshold(blurred_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Tampilkan hasil hitam-putih dari pemotongan di UI
        debug_image_window.image(thresholded_roi, caption="Kamera Intip Scanner (ROI Area)")

        # 4. Baca Barcode
        barcodes = pyzbar.decode(thresholded_roi, symbols=simbol_logistik)
        if not barcodes:
            # Fallback: jika Otsu Threshold gagal, coba baca gambar Grayscale biasa
            barcodes = pyzbar.decode(gray_roi, symbols=simbol_logistik)

        # --- PROSES BARCODE MULAI DI SINI ---
        for barcode in barcodes:
            barcode_data = barcode.data.decode("utf-8").strip()
            
            # Gambar kotak hijau mengelilingi letak barcode persis (relatif terhadap ROI)
            (b_x, b_y, b_w, b_h) = barcode.rect
            cv2.rectangle(frame, (x1 + b_x, y1 + b_y), (x1 + b_x + b_w, y1 + b_y + b_h), (0, 255, 0), 2)
            
            # 🔍 Validasi Panjang Karakter (Filter Port Code pendek)
            if len(barcode_data) < 10:
                continue
            
            # 🛑 Validasi Duplikasi Sesi: Skip jika baru saja terscan
            if barcode_data in st.session_state.resi_terscan_cache:
                cv2.putText(frame, "SUDAH TERDATA", (x1 + b_x, y1 + b_y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                continue
            
            # 💾 Simpan ke Database jika lolos validasi
            is_new = save_barcode_to_db(barcode_data)
            
            if is_new:
                # Masukkan ke dalam buffer memori
                st.session_state.resi_terscan_cache.add(barcode_data)
                
                # Update metrik angka & tabel di UI Streamlit
                total_placeholder.metric(label="Total Paket di Database", value=get_total_packages())
                df_updated = fetch_data_for_csv()
                table_placeholder.dataframe(df_updated, width='stretch', hide_index=True)
            
            # Indikator Sukses
            cv2.putText(frame, f"SUCCESS: {barcode_data}", (x1 + b_x, y1 + b_y - 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        # --- PROSES BARCODE SELESAI ---

        # Hitung durasi dan kalkulasi FPS
        process_time = time.time() - start_time
        if process_time > 0:
            fps = 1 / process_time
        else:
            fps = 0
            
        fps_small_display.caption(f"Kecepatan deteksi: {fps:.2f} FPS")
        
        # Render ke UI Utama
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_window.image(frame_rgb)

    cap.release()
else:
    # Menampilkan pesan standby ketika checkbox dimatikan
    st.write("⏸️ Scanner dalam keadaan standby. Silakan pilih sumber video dan centang 'Nyalakan Scanner'.")