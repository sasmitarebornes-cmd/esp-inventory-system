import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
# PENAMBAHAN: Library untuk akses fisik Google Drive
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
# 2. CSS OVERRIDE (TETAP SAMA)
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
    div[data-testid="metric-container"] {
        background-color: white !important;
        padding: 20px !important;
        border-radius: 10px !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05) !important;
        border-left: 5px solid #0e2135 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 3. LOAD API KEY (TETAP SAMA)
# ============================================================
def load_api_keys():
    keys = []
    if "GOOGLE_API_KEY" in st.secrets:
        keys.append(st.secrets["GOOGLE_API_KEY"])
    return keys

API_KEYS = load_api_keys()
MODEL_LIST = ["gemini-3-flash", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro"]

if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY ditemukan di Streamlit Secrets!")
    st.stop()

# ============================================================
# 4. KONEKSI GOOGLE SERVICES (SHEETS & DRIVE)
# ============================================================
@st.cache_resource
def init_google_services():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        
        # Inisialisasi Sheets
        gc = gspread.authorize(creds)
        sheet = gc.open("DATA INVENTORY PT.ESP").sheet1
        
        # PENAMBAHAN: Inisialisasi Drive Service
        drive_service = build('drive', 'v3', credentials=creds)
        
        return sheet, drive_service
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Google: {e}")
        return None, None

sheet, drive_service = init_google_services()

# ============================================================
# 5. HELPER DRIVE (PENAMBAHAN BARU UNTUK FILE FISIK)
# ============================================================
def get_or_create_folder(name, parent_id=None):
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id: query += f" and '{parent_id}' in parents"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    if files: return files[0]['id']
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id] if parent_id else []}
    return drive_service.files().create(body=meta, fields='id').execute().get('id')

def upload_to_drive(file_bytes, file_name, mime_type, client_name):
    ROOT_ID = "13wUu0PasVjyvVL9d4UEQkC_5EFddF2h3" # Folder Utama PT. ESP
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
# 6. LOGIKA ANALISIS (TETAP SAMA DENGAN MILIKMU)
# ============================================================
def get_file_hash(file_input):
    file_input.seek(0)
    data = file_input.read()
    h = hashlib.md5(data).hexdigest()
    file_input.seek(0)
    return h

def compress_image(file_input, max_size=(1024, 1024), quality=80):
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P", "LA"): img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf)

def build_content(file_input):
    instruksi = "Kamu adalah AI Inventory PT EKASARI PERKASA. Ekstrak informasi penting dari dokumen ini secara terstruktur."
    is_pdf = hasattr(file_input, 'type') and file_input.type == "application/pdf"
    file_input.seek(0)
    if is_pdf:
        return [{"mime_type": "application/pdf", "data": file_input.read()}, instruksi]
    else:
        return [compress_image(file_input), instruksi]

def proses_analisis_ai(file_input):
    if "ai_cache" not in st.session_state: st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    if fhash in st.session_state.ai_cache: return st.session_state.ai_cache[fhash]
    
    try: konten = build_content(file_input)
    except Exception as e: return f"❌ Gagal: {e}"

    for api_key in API_KEYS:
        genai.configure(api_key=api_key)
        for model_name in MODEL_LIST:
            try:
                mdl = genai.GenerativeModel(model_name)
                response = mdl.generate_content(konten)
                st.session_state.ai_cache[fhash] = response.text
                return response.text
            except: continue
    return "❌ Gagal Analisis."

# ============================================================
# 7. SIDEBAR (TETAP SAMA)
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        col_s1, col_s2, col_s3 = st.columns([1, 2, 1])
        with col_s2: st.image("ESP LOGO ICON RED WHITE.png", use_container_width=True)
    st.markdown("<h3 style='text-align: center; color: white;'>PT. EKASARI PERKASA</h3>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.caption("Build v9.5 - Drive Integration")

# ============================================================
# 8. SCAN & UPLOAD (PERBAIKAN BAGIAN PROSES SIMPAN)
# ============================================================
if menu == "📤 Scan & Upload":
    st.header("Ekasari Perkasa Inventory Dashboard")
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("Nama Perusahaan")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with c_b:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "PEB", "PIB","DOKAP", "Lainnya"])
        id_doc = st.text_input("ID Document")

    tab_upload, tab_camera = st.tabs(["📁 Upload File", "📷 Ambil Foto"])
    source_file = None
    with tab_upload:
        u_file = st.file_uploader("Pilih Dokumen", type=["pdf", "jpg", "png"], key="uploader")
        if u_file: source_file = u_file
    with tab_camera:
        cam_file = st.camera_input("Ambil Foto", key="camera")
        if cam_file: source_file = cam_file

    if source_file and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi Nama Perusahaan Ya Sayank :D")
        else:
            with st.spinner("Sedang Menganalisis & Mengunggah File..."):
                # 1. Analisis AI (Tetap seperti kodesu sebelumnya)
                hasil = proses_analisis_ai(source_file)
                
                if "❌" not in hasil and sheet:
                    try:
                        # 2. UPLOAD FISIK KE DRIVE (Penambahan Logika Baru)
                        source_file.seek(0)
                        bytes_data = source_file.read()
                        fname = getattr(source_file, 'name', 'camera_capture.jpg')
                        mtype = getattr(source_file, 'type', 'image/jpeg')
                        
                        link_drive = upload_to_drive(bytes_data, fname, mtype, nama_klien)
                        
                        # 3. SIMPAN KE GSHEETS (Menambahkan link_drive di kolom terakhir)
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([nama_klien, ts, id_doc if id_doc else fname, kategori, divisi, hasil, link_drive])
                        
                        st.success("✅ Berhasil disimpan di Drive & Sheets!")
                        st.info(hasil)
                        st.link_button("📂 Lihat File Fisik", link_drive)
                    except Exception as e:
                        st.error(f"Gagal Upload Fisik: {e}")
                else:
                    st.error(hasil)

# ... (Halaman Dashboard & Database tetap sama seperti milikmu)
elif menu == "🏠 Dashboard":
    st.markdown('<div class="header-box"><h1>PT. EKASARI PERKASA</h1></div>', unsafe_allow_html=True)
elif menu == "📑 Full Database":
    if sheet:
        data = pd.DataFrame(sheet.get_all_records())
        st.dataframe(data, use_container_width=True)
