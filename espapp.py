import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PIL import Image
import os
import time
import pandas as pd
import io

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. EKASARI PERKASA - SMART INVENTORY 2026",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS CUSTOM (PREMIUM STYLE)
# ============================================================
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6 !important; }
    [data-testid="stSidebar"] { background-color: #0e2135 !important; }
    [data-testid="stSidebar"] .stText,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] h1 { color: #ffffff !important; }
    
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
# 3. KONEKSI SERVICES (GSHEET, DRIVE, AI)
# ============================================================
def load_api_keys():
    return [st.secrets["GOOGLE_API_KEY"]] if "GOOGLE_API_KEY" in st.secrets else []

API_KEYS = load_api_keys()

# POWERED BY GEMINI 3 (2026 EDITION)
MODEL_LIST = [
    "gemini-3-flash", 
    "gemini-3-flash-preview", 
    "gemini-2.0-flash-exp" # Fallback terakhir
]

@st.cache_resource
def init_services():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        
        gc = gspread.authorize(creds)
        drive_service = build('drive', 'v3', credentials=creds)
        sheet = gc.open("DATA INVENTORY PT.ESP").get_worksheet(0)
        return sheet, drive_service
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Services: {e}")
        return None, None

sheet, drive_service = init_services()

# ============================================================
# 4. DRIVE AUTO-FOLDER & FIX QUOTA LOGIC
# ============================================================
def get_or_create_folder(folder_name, parent_id=None):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id else []
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(file_content, file_name, mime_type, client_name):
    ROOT_ID = "13wUu0PasVjyvVL9d4UEQkC_5EFddF2h3" 
    
    year_folder = time.strftime("%Y")
    month_folder = time.strftime("%B")
    
    id_tahun = get_or_create_folder(year_folder, ROOT_ID)
    id_bulan = get_or_create_folder(month_folder, id_tahun)
    
    full_name = f"{client_name}_{time.strftime('%H%M%S')}_{file_name}"
    file_metadata = {'name': full_name, 'parents': [id_bulan]}
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type, resumable=True)
    
    # 1. Upload ke Drive
    uploaded_file = drive_service.files().create(
        body=file_metadata, 
        media_body=media, 
        fields='id, webViewLink'
    ).execute()
    
    file_id = uploaded_file.get('id')

    # 2. FIX QUOTA: Transfer ownership ke Gmail utama agar storage robot gak penuh
    try:
        user_permission = {
            'type': 'user',
            'role': 'owner',
            'emailAddress': 'sasmitareborns@gmail.com' 
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=user_permission,
            transferOwnership=True
        ).execute()
    except:
        pass 

    return uploaded_file.get('webViewLink')

# ============================================================
# 5. HELPER & AI CORE
# ============================================================
def build_content(file_input, instruksi):
    file_input.seek(0)
    if hasattr(file_input, 'type') and file_input.type == "application/pdf":
        return [{"mime_type": "application/pdf", "data": file_input.read()}, instruksi]
    else:
        img = Image.open(file_input)
        if img.mode != 'RGB': img = img.convert('RGB')
        return [img, instruksi]

def proses_analisis_ai(file_input, client_name):
    instruksi = f"Kamu adalah AI Inventory PT EKASARI PERKASA. Analisis dokumen klien {client_name}. Ekstrak detail barang, berat, dan no dokumen secara profesional seperti format Air Waybill."
    
    for api_key in API_KEYS:
        genai.configure(api_key=api_key)
        for model_name in MODEL_LIST:
            try:
                model = genai.GenerativeModel(model_name)
                content = build_content(file_input, instruksi)
                response = model.generate_content(content)
                return response.text
            except:
                continue
    return "❌ Gagal. Model Gemini 3 tidak merespon."

# ============================================================
# 6. SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    side_col1, side_col2, side_col3 = st.columns([1, 3, 1])
    with side_col2:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", use_container_width=True)
    
    st.title("PT. EKASARI PERKASA") 
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    if st.button("🔄 System Refresh"):
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# 7. DASHBOARD
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    c_logo, c_txt = st.columns([1, 5], vertical_alignment="center") 
    with c_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=100)
    with c_txt:
        st.markdown("<h1 style='margin:0;'>PT. EKASARI PERKASA</h1><p style='margin:0;'>Smart Inventory Dashboard</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Dokumen", f"{len(df)}")
                s2.metric("Klien Terakhir", str(df.iloc[-1, 0]))
                st.subheader("📊 Transaksi Terbaru")
                st.dataframe(df.tail(10), use_container_width=True)
        except:
            st.info("👋 Selamat datang di PT. EKASARI PERKASA!")

# ============================================================
# 8. SCAN & UPLOAD
# ============================================================
elif menu == "📤 Scan & Upload":
    st.header("📤 Input Dokumen Inventory")
    col1, col2 = st.columns(2)
    with col1:
        nama_klien = st.text_input("Nama Perusahaan (Klien)")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with col2:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan" , "Lainnya"])
        id_doc = st.text_input("ID Document (No AWB/Invoice)")

    st.markdown("---")
    u_file = st.file_uploader("Upload File", type=["pdf", "jpg", "png"])
    
    if "cam_on" not in st.session_state: st.session_state.cam_on = False
    if st.button("📷 Buka/Tutup Kamera"):
        st.session_state.cam_on = not st.session_state.cam_on
        st.rerun()

    cam_shot = st.camera_input("Ambil Foto") if st.session_state.cam_on else None
    source = u_file if u_file else cam_shot

    if source and st.button("🚀 PROSES & SIMPAN", type="primary", use_container_width=True):
        if not nama_klien:
            st.warning("⚠️ Isi Nama Perusahaan dulu!")
        else:
            with st.spinner("🤖 Gemini 3 sedang menganalisa..."):
                hasil_ai = proses_analisis_ai(source, nama_klien)
                
                if "❌" not in hasil_ai:
                    source.seek(0)
                    file_bytes = source.read()
                    orig_name = getattr(source, 'name', 'camera_shot.jpg')
                    m_type = getattr(source, 'type', 'image/jpeg')
                    
                    try:
                        link_drive = upload_to_drive(file_bytes, orig_name, m_type, nama_klien)
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        sheet.append_row([
                            nama_klien, ts, id_doc if id_doc else "Auto", 
                            kategori, divisi, hasil_ai, link_drive
                        ])
                        
                        st.success("✅ Berhasil! Data Gemini 3 & Link Drive Tersimpan.")
                        st.info(f"📄 Hasil Analisis:\n{hasil_ai}")
                        st.link_button("📂 Buka File Original di Drive", link_drive)
                    except Exception as e:
                        st.error(f"Gagal upload: {e}")
                else:
                    st.error(hasil_ai)

# ============================================================
# 9. DATABASE
# ============================================================
elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        data = pd.DataFrame(sheet.get_all_records())
        st.dataframe(data, use_container_width=True)
        csv = data.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", csv, "Database_ESP.csv", "text/csv")
