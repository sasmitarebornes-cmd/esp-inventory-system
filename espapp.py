import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
# Tambahan library untuk akses file fisik ke Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image
import os
import time
import pandas as pd
import hashlib
import io

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. ESP - SMART INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS OVERRIDE (Sesuai permintaanmu)
# ============================================================
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6 !important; }
    [data-testid="stSidebar"] { background-color: #0e2135 !important; }
    [data-testid="stSidebar"] .stText,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] h1 { color: #ffffff !important; }
    div[data-testid="stSidebar"] div[role="radiogroup"] > label { color: white !important; }
    .header-box {
        background-color: white;
        padding: 20px 40px;
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 25px;
        border-bottom: 5px solid #d32f2f;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 3. KONEKSI GOOGLE SERVICES (SHEETS & DRIVE)
# ============================================================
@st.cache_resource
def init_google_services():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        # Scope untuk Sheets dan Drive fisik
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        
        # Inisialisasi Google Sheets
        gc = gspread.authorize(creds)
        sheet = gc.open("DATA INVENTORY PT.ESP").sheet1
        
        # Inisialisasi Google Drive (Untuk simpan file fisik)
        drive_service = build('drive', 'v3', credentials=creds)
        
        return sheet, drive_service
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Google: {e}")
        return None, None

sheet, drive_service = init_google_services()

# ============================================================
# 4. FUNGSI UPLOAD DRIVE (LOGIKA FOLDER)
# ============================================================
def get_or_create_folder(name, parent_id=None):
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id: query += f" and '{parent_id}' in parents"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    if files: return files[0]['id']
    
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id] if parent_id else []}
    folder = drive_service.files().create(body=meta, fields='id').execute()
    return folder.get('id')

def upload_to_drive(file_bytes, file_name, mime_type, client_name):
    # ID Folder Utama "EKASARI DATA INVENTORY"
    ROOT_ID = "13wUu0PasVjyvVL9d4UEQkC_5EFddF2h3" 
    
    # Otomatis buat/cari folder Tahun -> Bulan
    id_tahun = get_or_create_folder(time.strftime("%Y"), ROOT_ID)
    id_bulan = get_or_create_folder(time.strftime("%B"), id_tahun)
    
    new_name = f"{client_name}_{time.strftime('%H%M%S')}_{file_name}"
    meta = {'name': new_name, 'parents': [id_bulan]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    
    file_drive = drive_service.files().create(
        body=meta, media_body=media, fields='webViewLink', supportsAllDrives=True
    ).execute()
    return file_drive.get('webViewLink')

# ============================================================
# 5. LOGIKA ANALISIS AI (IDENTIK DENGAN MILIKMU)
# ============================================================
def get_file_hash(file_input):
    file_input.seek(0)
    data = file_input.read()
    h = hashlib.md5(data).hexdigest()
    file_input.seek(0)
    return h

def compress_image(file_input):
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P", "LA"): img = img.convert("RGB")
    img.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    buf.seek(0)
    return Image.open(buf)

def proses_analisis_ai(file_input):
    if "ai_cache" not in st.session_state: st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    if fhash in st.session_state.ai_cache: return st.session_state.ai_cache[fhash]

    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        MODEL_LIST = [
    "gemini-3-flash",                # Model utama tahun 2026
    "gemini-3-flash-preview",        # Versi preview terbaru
    "gemini-3.1-flash-lite-preview", # Versi hemat kuota
    "gemini-2.5-pro"                 # Fallback seri 2.5
]
        
        is_pdf = hasattr(file_input, 'type') and file_input.type == "application/pdf"
        file_input.seek(0)
        
        if is_pdf:
            konten = [{"mime_type": "application/pdf", "data": file_input.read()}, "Ekstrak data dokumen PT EKASARI PERKASA ini."]
        else:
            konten = [compress_image(file_input), "Ekstrak data dokumen PT EKASARI PERKASA ini."]
            
        response = model.generate_content(konten)
        st.session_state.ai_cache[fhash] = response.text
        return response.text
    except Exception as e:
        return f"❌ Error AI: {e}"

# ============================================================
# 6. SIDEBAR & MENU
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2: st.image("ESP LOGO ICON RED WHITE.png", use_container_width=True)
    st.markdown("<h3 style='text-align: center; color: white;'>PT. EKASARI PERKASA</h3>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.caption("Build v9.5 - Final Clean")

# ============================================================
# 7. HALAMAN SCAN & UPLOAD (BAGIAN KRUSIAL)
# ============================================================
if menu == "📤 Scan & Upload":
    st.header("Ekasari Perkasa Inventory Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        nama_klien = st.text_input("Nama Perusahaan")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with col2:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "PEB", "PIB", "Lainnya"])
        id_doc = st.text_input("ID Document")

    source_file = st.file_uploader("Upload File", type=["pdf", "jpg", "png"])
    cam_file = st.camera_input("Atau Gunakan Kamera")
    
    input_final = source_file if source_file else cam_file

    if input_final and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi Nama Perusahaan dulu ya Sayank :D")
        else:
            with st.spinner("System sedang Menganalisis Data..."):
                # 1. Jalankan Analisis AI
                hasil_ai = proses_analisis_ai(input_final)
                
                if "❌" not in hasil_ai:
                    try:
                        # 2. PROSES UPLOAD FISIK (Ini yang membuat folder tidak kosong)
                        input_final.seek(0)
                        bytes_data = input_final.read()
                        fname = getattr(input_final, 'name', 'camera_capture.jpg')
                        mtype = getattr(input_final, 'type', 'image/jpeg')
                        
                        # Upload ke Drive dan dapatkan Link
                        link_drive = upload_to_drive(bytes_data, fname, mtype, nama_klien)
                        
                        # 3. Simpan Ke GSheets (Ditambah link drive di kolom terakhir)
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([nama_klien, ts, id_doc if id_doc else fname, kategori, divisi, hasil_ai, link_drive])
                        
                        st.success("✅ BERHASIL! File tersimpan di Google Drive & Data tercatat.")
                        st.link_button("📂 Lihat File di Drive", link_drive)
                        st.info(hasil_ai)
                    except Exception as e:
                        st.error(f"Gagal Simpan Fisik: {e}")
                else:
                    st.error(hasil_ai)

# ============================================================
# 8. DASHBOARD & DATABASE (IDENTIK MILIKMU)
# ============================================================
elif menu == "🏠 Dashboard":
    st.markdown('<div class="header-box"><h1>PT. EKASARI PERKASA</h1><p>Sistem Inventory Otomatis</p></div>', unsafe_allow_html=True)
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            st.metric("Total Dokumen", len(df))
            st.dataframe(df.tail(5), use_container_width=True)

elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        st.dataframe(df, use_container_width=True)
