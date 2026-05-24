#abaikan code ini
# !pip install python-barcode pillow

import barcode
from barcode.writer import ImageWriter

# Ambil nomor resi asli dari Tokopedia atau buat acak
no_resi_list = ["JX9420705938", "JX9413525967", "JX9393656090", "JX7254370613", "JX7204315485", "JX3506983719", "JX3470615855", "JT0951495356","JT0348351866"]

# Set format ke Code 128 (standar logistik/paket)
code128 = barcode.get_barcode_class('code128')

for index, resi in enumerate(no_resi_list):
    # Generate barcode dan simpan sebagai file PNG
    my_barcode = code128(resi, writer=ImageWriter())
    filename = f"sample_barcode_{index + 1}"
    my_barcode.save(filename)
    print(f"Berhasil membuat: {filename}.png")