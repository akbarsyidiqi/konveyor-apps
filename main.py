import cv2
import numpy as np
from ultralytics import YOLO
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol
import streamlit as st
import time
import sqlite3
import pandas as pd

# ==========================================
# 1. INISIALISASI DATABASE (SQLite)
# ==========================================

# Menghapus seluruh cache data dan cache resource di Streamlit
# st.cache_data.clear()
# st.cache_resource.clear()

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
st.write("Sistem Pemindaian Paket Otomatis Berbasis AI (YOLOv8 + PyZbar + SQLite)")

# Load Model YOLOv8 (Pastikan file best.pt hasil Roboflow ada di folder yang sama)
@st.cache_resource
def load_yolo_model():
    return YOLO("best.pt")

model = load_yolo_model()

# Layout Kolom Dashboard
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📹 Live Camera Feed & Object Detection")
    
    sumber_video = st.radio("Pilih Sumber Video:", ("Video Demo di Repo (MP4)", "Kamera HP (URL Stream)"))
    
    url_kamera_hp = ""
    if sumber_video == "Kamera HP (URL Stream)":
        # Dummy IP
        url_kamera_hp = st.text_input(
            "🔗 Masukkan URL Video dari HP:", 
            value="http://192.168.1.5:8080/video" 
        )
        st.caption("Gunakan aplikasi seperti 'IP Webcam' di Android.")
    
    # Tambahkan petunjuk UX agar user/juri tahu urutan penggunaannya
    st.info("💡 SOP: Matikan centang (uncheck) di bawah ini terlebih dahulu sebelum mengganti sumber video/URL.")
    
    run_scanner = st.checkbox("Nyalakan Scanner", value=False)
    frame_window = st.image([], width="stretch")

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
    
    st.write("🔍 **Kotak Intip Scanner (Otsu)**")
    debug_image_window = st.image([], width='stretch')

# ==========================================
# 3. CORE PROCESSING LOOP (OpenCV + Vision)
# ==========================================

# Kamera HANYA diinisialisasi jika checkbox menyala
if run_scanner:
    if sumber_video == "Kamera HP (URL Stream)":
        video_source = url_kamera_hp
    else:
        #video_source = "video-resi-jarak-30cm.mp4" 
        video_source = "video-resi-jarak-30cm-terbaca-semua.mp4"

    cap = cv2.VideoCapture(video_source)

    # 💾 BUFFER MEMORI: Menyimpan resi yang sudah sukses dipindai di sesi ini
    # agar tidak discan ulang secara terus menerus
    if 'resi_terscan_cache' not in st.session_state:
        st.session_state.resi_terscan_cache = set()

    # Sapu bersih "cache visual" atau sisa gambar hantu dari sesi sebelumnya 
    # tepat sebelum video baru diputar
    debug_image_window.empty()

    # Tambahkan variabel penghitung frame
    frame_count = 0 
    
    # Tambahkan frame skip (semakin besar angkanya, semakin ringan, tapi video sedikit patah)
    # Angka 3 artinya kita hanya memproses 1 dari setiap 3 frame
    frame_skip = 3

    while cap.isOpened():
        start_time = time.time() # Catat waktu mulai
        ret, frame = cap.read()
        
        if not ret:
            break

        frame_count += 1
        
        # JIKA BUKAN KELIPATAN FRAME_SKIP, LEWATI DETEKSI!
        if frame_count % frame_skip != 0:
            continue
            
        if sumber_video == "Video Demo di Repo (MP4)":
            time.sleep(0.01) # Kurangi delay sleep jika masih terlalu lambat
        
        # Deteksi objek menggunakan YOLO
        results = model(frame, verbose=False)
    
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                h, w, _ = frame.shape
                pad = 20
                crop_x1, crop_y1 = max(0, x1 - pad), max(0, y1 - pad)
                crop_x2, crop_y2 = min(w, x2 + pad), min(h, y2 + pad)
                
                cropped_package = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                
                if cropped_package.size > 0:
                    gray = cv2.cvtColor(cropped_package, cv2.COLOR_BGR2GRAY)
                    _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    debug_image_window.image(thresholded, caption="Kamera Intip Scanner")

                    simbol_logistik = [
                        ZBarSymbol.CODE128, ZBarSymbol.CODE39, ZBarSymbol.EAN13, 
                        ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.QRCODE
                    ]

                    barcodes = pyzbar.decode(thresholded, symbols=simbol_logistik)
                    
                    if not barcodes:
                        barcodes = pyzbar.decode(gray, symbols=simbol_logistik)
                    
                    # --- PROSES BARCODE MULAI DI SINI ---
                    import re

                    for barcode in barcodes:
                        barcode_data = barcode.data.decode("utf-8").strip()
                        
                        # 🔍 1. Validasi Panjang Karakter (Filter Port Code)
                        if len(barcode_data) < 10:
                            # Ini Port Code, abaikan
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            continue
                        
                        # 🛑 2. Validasi Duplikasi: Jika resi sudah pernah terscan di sesi ini, LANGSUNG SKIP
                        if barcode_data in st.session_state.resi_terscan_cache:
                            # Beri penanda visual tipis bahwa paket ini sudah diproses (Optional)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2) # Kotak Kuning = Sudah Terdata
                            cv2.putText(frame, "SUDAH TERDATA (SKIP)", (x1, y1 - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                            continue  # <--- Melompat langsung ke barcode/paket berikutnya
                        
                        # 💾 3. Jika resi BARU, masukkan ke database
                        is_new = save_barcode_to_db(barcode_data)
                        
                        if is_new:
                            # Masukkan ke dalam buffer memori agar tidak diproses lagi di frame selanjutnya
                            st.session_state.resi_terscan_cache.add(barcode_data)
                            
                            # Update metrik angka & tabel di UI Streamlit
                            total_placeholder.metric(label="Total Paket di Database", value=get_total_packages())
                            df_updated = fetch_data_for_csv()
                            table_placeholder.dataframe(df_updated, width='stretch', hide_index=True)
                        
                        # Efek Visual untuk Resi yang BARU SUKSES TERSCAN
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 4)
                        cv2.putText(frame, f"SUCCESS: {barcode_data}", (x1, y1 - 30), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    # --- PROSES BARCODE SELESAI ---

        # Hitung durasi (berapa detik yang dihabiskan untuk memproses 1 frame)
        process_time = time.time() - start_time
        
        # Menghindari pembagian dengan nol
        if process_time > 0:
            fps = 1 / process_time
        else:
            fps = 0
            
        fps_small_display.caption(f"Kecepatan deteksi: {fps:.2f} FPS")
        
        # Tampilkan ke UI
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_window.image(frame_rgb)

    cap.release()
else:
    # Menampilkan pesan standby ketika checkbox dimatikan
    st.write("⏸️ Scanner dalam keadaan standby. Silakan pilih sumber video dan centang 'Nyalakan Scanner'.")