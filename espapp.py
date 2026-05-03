import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from PIL import Image
import os
import time
import pandas as pd
import hashlib
import io
import mimetypes
from datetime import datetime

# 🔹 Safe import untuk Drive API (tidak crash jika library belum terinstall)
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    DRIVE_LIB_AVAILABLE = True
except ImportError:
    DRIVE_LIB_AVAILABLE = False

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. ESP - SMART INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS OVERRIDE
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
# 3. LOAD API KEY
# ============================================================
def load_api_keys():
    keys = []
    if "GOOGLE_API_KEY" in st.secrets:
        keys.append(st.secrets["GOOGLE_API_KEY"])
    return keys

API_KEYS = load_api_keys()

MODEL_LIST = [
    "gemini-3-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-pro"
]

if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY ditemukan di Streamlit Secrets!")
    st.stop()

# ============================================================
# 4. KONEKSI GOOGLE SHEETS & DRIVE
# ============================================================
@st.cache_resource
def init_gsheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        st.session_state.drive_creds = creds
        return gc.open("DATA INVENTORY PT.ESP").sheet1
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Sheets: {e}")
        return None

sheet = init_gsheet()

# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================
def get_file_hash(file_input):
    file_input.seek(0)
    h = hashlib.md5(file_input.read()).hexdigest()
    file_input.seek(0)
    return h

def compress_image(file_input, max_size=(1024, 1024), quality=80):
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return buf

def build_content(file_input):
    instruksi = (
        "Kamu adalah AI Inventory PT ESP. "
        "Ekstrak informasi penting dari dokumen ini: "
        "Semua detail dokumen, "
        "Sajikan secara ringkas dan terstruktur. "
        "Lakukan deep analyze."
    )
    if file_input.type == "application/pdf":
        file_input.seek(0)
        pdf_data = file_input.read()
        return [{"mime_type": "application/pdf", "data": pdf_data}, instruksi]
    else:
        buf = compress_image(file_input)
        return [Image.open(buf), instruksi]

# ============================================================
# 6. GOOGLE DRIVE UPLOAD (FINAL CLEAN VERSION)
# ============================================================
def upload_to_drive(file_input, company_name, category, doc_id=None):
    if not DRIVE_LIB_AVAILABLE:
        return None, "⚠️ Library google-api-python-client belum terinstall. Skip upload Drive."
    
    try:
        creds = st.session_state.get("drive_creds")
        if not creds:
            return None, "❌ Kredensial Drive tidak tersedia"
        
        # Ambil Folder ID dari secrets (fallback ke root jika kosong)
        folder_id = st.secrets.get("DRIVE_FOLDER_ID", "root")
        
        # Prepare file data
        file_input.seek(0)
        file_bytes = file_input.read()
        filename = file_input.name or f"DOC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        mime_type = file_input.type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        now = datetime.now()
        folder_structure = [
            company_name.strip(),
            str(now.year),
            now.strftime("%Y-%m-%d"),
            category
        ]
        
        drive_service = build("drive", "v3", credentials=creds)
        parent_id = folder_id  # ✅ Mulai dari folder yang di-share
        
        for folder_name in folder_structure:
            query = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{folder_name}' "
                f"and '{parent_id}' in parents "
                f"and trashed=false"
            )
            results = drive_service.files().list(
                q=query, spaces="drive", fields="files(id, name)", supportsAllDrives=True
            ).execute()
            folders = results.get("files", [])
            
            if folders:
                parent_id = folders[0]["id"]
            else:
                folder_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id]
                }
                folder = drive_service.files().create(
                    body=folder_metadata, fields="id", supportsAllDrives=True
                ).execute()
                parent_id = folder.get("id")
        
        file_metadata = {
            "name": f"{doc_id}_{filename}" if doc_id else filename,
            "parents": [parent_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True
        ).execute()
        
        return uploaded_file.get("webViewLink"), None
        
    except Exception as e:
        return None, f"❌ Drive Upload Error: {str(e)}"

# ============================================================
# 7. FUNGSI ANALISIS AI
# ============================================================
def proses_analisis_ai(file_input):
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    
    if fhash in st.session_state.ai_cache:
        st.toast("⚡ Hasil dari cache.", icon="✅")
        return st.session_state.ai_cache[fhash]

    try:
        konten = build_content(file_input)
    except Exception as e:
        return f"❌ Gagal membaca file: {e}"

    for api_key in API_KEYS:
        genai.configure(api_key=api_key)
        for model_name in MODEL_LIST:
            try:
                mdl = genai.GenerativeModel(model_name)
                response = mdl.generate_content(konten)
                hasil = response.text
                st.session_state.ai_cache[fhash] = hasil
                return hasil
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["404", "not found", "model"]):
                    continue
                if any(x in err for x in ["429", "quota", "exhausted"]):
                    st.toast("⚠️ Limit terdeteksi, mencoba model berikutnya...", icon="🔄")
                    continue
                return f"❌ Error API: {e}"

    return "❌ Gagal. Pastikan Billing aktif dan model didukung."

# ============================================================
# 8. SIDEBAR & MENU
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. EKASARI PERKASA DATABASE")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Key aktif: **{len(API_KEYS)}**")
    st.caption("Build v8.2 - 2026 Gemini 3 + Drive Clean Integration")

# ============================================================
# 9. MAIN APP LOGIC
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 5])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=110)
    with col_text:
        st.markdown("<h1 style='margin:0; color:#0e2135;'>PT. EKASARI PERKASA</h1>", unsafe_allow_html=True)
        st.markdown("<p style='margin:0; color:#666;'>Sistem Inventory Data Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                with s1: st.metric("Total Dokumen", f"{len(df)} Unit")
                with s2: st.metric("Klien Terakhir", str(df.iloc[-1, 0]))
                with s3: st.metric("Update", str(df.iloc[-1, 1]).split(" ")[0])
                st.dataframe(df.tail(10), use_container_width=True)
        except: st.info("Dashboard siap!")

elif menu == "📤 Scan & Upload":
    st.header("📤 Ekasari Perkasa Inventory Dashboard")
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("Nama Perusahaan")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with c_b:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan" , "PEB" , "PIB" , "SPPB" , "Lainnya"])
        id_doc = st.text_input("ID Document (No AWB/Invoice)")

    st.markdown("---")
    upload_method = st.radio("📥 Metode Input", ["📁 Upload File", "📷 Gunakan Kamera"], horizontal=True)
    
    u_file = None
    
    if upload_method == "📁 Upload File":
        u_file = st.file_uploader("Upload Dokumen (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key="file_uploader")
    else:
        st.info(" Kamera hanya aktif setelah Anda menekan tombol di bawah")
        u_file = st.camera_input(" Ambil Foto Dokumen", key="camera_input")

    upload_to_drive_option = st.checkbox("🗂️ Simpan file fisik ke Google Drive", value=True)

    if u_file and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi dulu Nama Perusahaannya Ya Sayank muach :-D ")
        else:
            with st.spinner("System Sedang Menganalisis..."):
                hasil = proses_analisis_ai(u_file)
                if "❌" not in hasil and sheet:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    doc_name = id_doc if id_doc else u_file.name
                    
                    drive_link = None
                    if upload_to_drive_option:
                        with st.spinner(" Mengupload file ke Google Drive..."):
                            drive_link, drive_error = upload_to_drive(u_file, nama_klien, kategori, doc_name)
                            if drive_error:
                                st.warning(drive_error)
                            elif drive_link:
                                st.success(f" File tersimpan di Drive: [Link]({drive_link})")
                    
                    sheet.append_row([nama_klien, ts, doc_name, kategori, divisi, f"{hasil}\n\n📎 Drive: {drive_link}" if drive_link else hasil])
                    st.success("✅ Berhasil disimpan ke Database!")
                    with st.expander("📋 Hasil Analisis AI"):
                        st.info(hasil)
                else:
                    st.error(hasil)

elif menu == " Full Database":
    st.header(" Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                search_term = st.text_input("🔍 Cari dokumen...", placeholder="Nama perusahaan / ID / Kategori")
                if search_term:
                    data = data[data.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)]
                st.dataframe(data, use_container_width=True)
                csv = data.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 Download sebagai CSV", data=csv, file_name="inventory_esp.csv", mime="text/csv")
            else:
                st.info("📭 Belum ada data dalam database")
        except Exception as e: 
            st.error(f"Error: {e}")
