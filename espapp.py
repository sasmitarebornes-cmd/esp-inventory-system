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

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. ESP - SMART INVENTORY 2026",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS CUSTOM (PREMIUM PT. ESP STYLE)
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
    .status-badge {
        background-color: #00e676;
        color: #000;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: bold;
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
# 3. LOAD API KEY & MODEL LIST (GEMINI 3)
# ============================================================
def load_api_keys():
    return [st.secrets["GOOGLE_API_KEY"]] if "GOOGLE_API_KEY" in st.secrets else []

API_KEYS = load_api_keys()

# Menggunakan model Gemini terbaru tahun 2026
MODEL_LIST = [
    "gemini-3-flash", 
    "gemini-3-flash-preview", 
    "gemini-2.0-flash-exp" # Fallback
]

if not API_KEYS:
    st.error("❌ API KEY TIDAK DITEMUKAN!")
    st.stop()

# ============================================================
# 4. KONEKSI GOOGLE SHEETS
# ============================================================
@st.cache_resource
def init_gsheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open("DATA INVENTORY PT.ESP").get_worksheet(0)
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Sheets: {e}")
        return None

sheet = init_gsheet()

# ============================================================
# 5. HELPER & AI CORE
# ============================================================
def get_file_hash(file_input):
    file_input.seek(0)
    return hashlib.md5(file_input.read()).hexdigest()

def build_content(file_input, instruksi):
    if hasattr(file_input, 'type') and file_input.type == "application/pdf":
        file_input.seek(0)
        return [{"mime_type": "application/pdf", "data": file_input.read()}, instruksi]
    else:
        # Untuk Gambar/Kamera
        img = Image.open(file_input)
        if img.mode != 'RGB': img = img.convert('RGB')
        return [img, instruksi]

def proses_analisis_ai(file_input, client_name):
    instruksi = f"Kamu adalah AI Inventory PT ESP. Analisis dokumen klien {client_name}. Ekstrak detail barang, berat, dan no dokumen secara profesional."
    
    for api_key in API_KEYS:
        genai.configure(api_key=api_key)
        for model_name in MODEL_LIST:
            try:
                model = genai.GenerativeModel(model_name)
                content = build_content(file_input, instruksi)
                response = model.generate_content(content)
                return response.text
            except Exception:
                continue
    return "❌ Gagal. Model Gemini 3 tidak merespon atau kuota habis."

# ============================================================
# 6. SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    # Membuat logo presisi di tengah menggunakan kolom
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
    # vertical_alignment="center" memastikan logo sejajar tengah dengan teks
    c_logo, c_txt = st.columns([1, 5], vertical_alignment="center") 
    with c_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=100)
    with c_txt:
        st.markdown("<h1 style='margin:0;'>PT. EKASARI PERKASA</h1>", unsafe_allow_html=True)
        st.markdown("<p style='margin:0;'>Inventory Dashboard</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            df.columns = df.columns.str.strip()
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Dokumen", f"{len(df)}")
                s2.metric("Klien Terakhir", str(df.iloc[-1, 0]))
                if "Tanggal" in df.columns:
                    s3.metric("Update", str(df.iloc[-1]['Tanggal']).split()[0])
                st.subheader("📊 Transaksi Terbaru")
                st.dataframe(df.tail(10), use_container_width=True)
        except:
            st.info("👋 Selamat datang di Sistem Inventory PT. ESP!")

# ============================================================
# 8. SCAN & UPLOAD (DENGAN KAMERA)
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
            st.warning("⚠️ Isi Nama Perusahaan dulu ya sayank!")
        else:
            with st.spinner("🤖 AI Gemini 3 sedang bekerja..."):
                hasil = proses_analisis_ai(source, nama_klien)
                if "❌" not in hasil:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([nama_klien, ts, id_doc if id_doc else "Auto", kategori, divisi, hasil])
                    st.success("✅ Data Berhasil Masuk ke Database PT. ESP!")
                    st.info(hasil)
                else:
                    st.error(hasil)

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
