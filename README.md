# 📦 Smart Conveyor Barcode Scanner System

Sistem prototipe otomasi penyortiran logistik berbasis AI (Computer Vision) untuk membaca resi paket secara *real-time* di atas konveyor. Proyek ini menggabungkan Object Detection dan Barcode Processing menjadi satu *pipeline* arsitektur yang *production-ready*.

## 🚀 Fitur Utama
* **AI Object Detection:** Menggunakan model YOLOv8 untuk mendeteksi region paket/kardus (mengabaikan *background* visual yang tidak perlu).
* **Robust Barcode Scanning:** Terintegrasi dengan PyZbar dan filter binarisasi Otsu's Thresholding untuk membaca resi di berbagai tingkat pencahayaan (termasuk pada paket berwarna hitam).
* **Data Persistence:** Penyimpanan data nomor resi secara persisten menggunakan SQLite untuk mencegah duplikasi *scan*.
* **REST API Terintegrasi:** Dilengkapi *background service* menggunakan Flask untuk mengekspos data *scan* ke sistem operasional gudang lainnya.
* **Real-time Dashboard & Export:** Antarmuka pemantauan *real-time* berbasis Streamlit yang dilengkapi fitur unduh data ke format CSV.

## 🛠️ Teknologi yang Digunakan
* **Python 3.9+**
* **Computer Vision:** OpenCV (Headless), YOLOv8 (Ultralytics)
* **Barcode Processing:** PyZbar
* **Backend & Database:** Flask, SQLite3
* **Frontend UI:** Streamlit, Pandas

## ⚙️ Persyaratan Sistem
Jika menjalankan sistem ini di lingkungan server berbasis Linux (seperti Hugging Face Spaces, Ubuntu, atau Streamlit Cloud), pastikan OS sudah menginstal pustaka pembaca C-library berikut:
```bash
sudo apt-get install libzbar0
```

## Cara Kerja Aplikasi: 
* Clone repositori ini: https://github.com/akbarsyidiqi/konveyor-apps
* Instal dependensi Python: pip install -r requirements.txt
* Di terminal exec: python -m streamlit run main.py
* lalu browser akan membuka halaman http://localhost:8501/ ini adalah UI Aplikasi Utama
* SOP: Matikan centang Nyalakan Scanner (uncheck) terlebih dahulu sebelum mengganti sumber video/URL.
* Pilih "Video Demo". Untuk mencoba hasil scan dari Video Sampel
* Centang "Nyalakan Scanner". Video MP4 akan berputar.
* Matikan centang "Nyalakan Scanner". Video akan berhenti.
* Pindah radio button ke "Kamera HP".
* Ketik URL IP Webcam yang valid dari HP kamu. Install Aplikasi IP Webcam di playstore, buka lalu disana akan ada IP alamat stream. Masukan ke browser dan Start Server dan lakukan scan paket secara mandiri.
* Centang kembali "Nyalakan Scanner". Aliran video (stream) dari HP kamu sekarang akan langsung masuk dengan mulus!

## 📡 Dokumentasi REST API
* Sistem ini menjalankan background thread API yang bisa diakses secara lokal.
* Endpoint: GET /api/resi
* URL Lokal: http://localhost:5000/api/resi
* Response Output:
```
{
  "status": "success",
  "total_paket": 2,
  "data": [
    {
      "nomor_resi": "JP123456789",
      "waktu_scan": "2026-05-24 13:15:22"
    }
  ]
}
```