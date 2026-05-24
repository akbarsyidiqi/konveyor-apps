!pip install roboflow
!pip install ultralytics

from roboflow import Roboflow
rf = Roboflow(api_key="ll7aP78y9rXLHa9WHOhN")
project = rf.workspace("akbars-workspace-jguzc").project("video-resi-simulasi-conveyor")
version = project.version(1)
dataset = version.download("yolov8")

from ultralytics import YOLO

# 1. Load model YOLOv8 ukuran Small yang pre-trained
model = YOLO('yolov8s.pt') 

# 2. Mulai training dengan dataset kustom kamu
results = model.train(
    data=f"{dataset.location}/data.yaml", 
    epochs=50,       # Model akan belajar bolak-balik sebanyak 50 kali
    imgsz=640,       # Ukuran resolusi gambar standar YOLO
    plots=True       # Menghasilkan grafik akurasi untuk bahan presentasi nanti
)

from google.colab import files

# Mengunduh file bobot model terbaik ke komputer kamu
files.download('/content/runs/detect/train/weights/best.pt')

# Mengambil Grafik untuk Bahan Slide Presentasi
import cv2
import matplotlib.pyplot as plt

# Membaca gambar hasil visualisasi training YOLOv8
results_img = cv2.imread('/content/runs/detect/train/results.png')
results_img = cv2.cvtColor(results_img, cv2.COLOR_BGR2RGB)

plt.figure(figsize=(12, 10))
plt.imshow(results_img)
plt.axis('off')
plt.show()
                