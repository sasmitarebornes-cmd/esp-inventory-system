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

# PERBAIKAN 2026: Menggunakan model Gemini terbaru seri 3 & 2.5
MODEL_LIST = [
    "gemini-3-flash",                # Model utama tahun 2026
    "gemini-3-flash-preview",        # Versi preview terbaru
    "gemini-3.1-flash-lite-preview", # Versi hemat kuota
    "gemini-2.5-pro"                 # Fallback seri 2.5
]

if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY ditemukan di Streamlit Secrets!")
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
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
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
    return Image.open(buf)

def build_content(file_input):
    instruksi = (
        "Kamu adalah AI Inventory PT ESP. "
        "Ekstrak informasi penting dari dokumen ini: "
        "Semua detail dokumen, "
        "Sajikan secara ringkas dan terstruktur."
        "Lakukan deep analyze."
    )
    if file_input.type == "application/pdf":
        file_input.seek(0)
        pdf_data = file_input.read()
        return [{"mime_type": "application/pdf", "data": pdf_data}, instruksi]
    else:
        file_input.seek(0)
        return [compress_image(file_input), instruksi]

# ============================================================
# 6. FUNGSI ANALISIS AI
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

    return "❌ Gagal. Pastikan Billing aktif dan model didukung di tahun 2026."

# ============================================================
# 7. SIDEBAR & MENU (Bagian selanjutnya tetap sama)
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. EKASARI PERKASA DATABASE")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Key aktif: **{len(API_KEYS)}**")
    st.caption("Build v8.0 - 2026 Gemini 3 Engine")

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

    u_file = st.file_uploader("Upload Dokumen (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"])

    if u_file and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi Nama Perusahaannya Ya Sayank muach :-D")
        else:
            with st.spinner("AI Menganalisis dengan Gemini 3..."):
                hasil = proses_analisis_ai(u_file)
                if "❌" not in hasil and sheet:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([nama_klien, ts, id_doc if id_doc else u_file.name, kategori, divisi, hasil])
                    st.success("✅ Berhasil disimpan!")
                    st.info(hasil)
                else:
                    st.error(hasil)

elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            st.dataframe(data, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")
