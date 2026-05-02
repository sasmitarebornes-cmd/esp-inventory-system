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
# 2. CSS OVERRIDE (PROFESSIONAL LOOK & MOBILE OPTIMIZED)
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
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border-left: 10px solid #d32f2f;
    }
    .status-online {
        color: #00ff00;
        font-size: 0.8rem;
        font-weight: bold;
    }
    div[data-testid="metric-container"] {
        background-color: white !important;
        padding: 15px !important;
        border-radius: 12px !important;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05) !important;
        border-bottom: 4px solid #0e2135 !important;
    }
    /* Memastikan tombol besar di HP */
    .stButton button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 3. LOAD API KEY & MODEL CONFIG (VERSI 2026)
# ============================================================
def load_api_keys():
    keys = []
    if "GOOGLE_API_KEY" in st.secrets:
        keys.append(st.secrets["GOOGLE_API_KEY"])
    return keys

API_KEYS = load_api_keys()
MODEL_LIST = ["gemini-3-flash", "gemini-3-flash-preview", "gemini-2.5-pro"]

# ============================================================
# 4. KONEKSI GOOGLE SHEETS
# ============================================================
@st.cache_resource
def init_gsheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            # Mengatasi masalah parsing karakter \n dari secrets
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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
def get_file_hash(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()

def process_image_for_ai(image_input):
    img = Image.open(image_input)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return Image.open(buf)

def build_content(file_input, is_pdf=False):
    instruksi = (
        "Kamu adalah AI Inventory Expert PT ESP. "
        "Ekstrak: No AWB/Invoice, Nama Pengirim, Nama Penerima, "
        "Deskripsi Barang, Berat, dan Jumlah. "
        "Sajikan dalam format ringkas dan profesional."
    )
    if is_pdf:
        return [{"mime_type": "application/pdf", "data": file_input}, instruksi]
    else:
        return [process_image_for_ai(file_input), instruksi]

# ============================================================
# 6. FUNGSI ANALISIS AI
# ============================================================
def proses_analisis_ai(file_data, is_pdf=False):
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    
    # Hash check untuk hemat kuota
    fhash = get_file_hash(file_data if is_pdf else file_data.getvalue())
    if fhash in st.session_state.ai_cache:
        return st.session_state.ai_cache[fhash]

    try:
        konten = build_content(file_data, is_pdf)
        for api_key in API_KEYS:
            genai.configure(api_key=api_key)
            for model_name in MODEL_LIST:
                try:
                    mdl = genai.GenerativeModel(model_name)
                    response = mdl.generate_content(konten)
                    st.session_state.ai_cache[fhash] = response.text
                    return response.text
                except Exception:
                    continue
        return "❌ Limit API tercapai. Coba lagi nanti."
    except Exception as e:
        return f"❌ Gagal Analisis: {e}"

# ============================================================
# 7. SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. ESP DATA")
    st.markdown("<p class='status-online'>● SYSTEM ONLINE v8.6</p>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    if st.button("🔄 Refresh System"):
        st.cache_resource.clear()
        st.rerun()
    st.caption("Build with Gemini 3 Engine")

# ============================================================
# 8. HALAMAN: DASHBOARD
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    st.markdown("<h1 style='margin:0; color:#0e2135;'>DASHBOARD</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0; color:#666;'>PT. EKASARI PERKASA - Smart Inventory</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Data", f"{len(data)} Dokumen")
                c2.metric("Divisi EXPORT", f"{len(data[data['Divisi']=='EXPORT'])}")
                c3.metric("Divisi IMPORT", f"{len(data[data['Divisi']=='IMPORT'])}")
                
                st.subheader("📌 Aktivitas Terakhir")
                st.dataframe(data.tail(10), use_container_width=True)
            else:
                st.info("Sistem siap. Belum ada data yang masuk hari ini.")
        except:
            st.info("Menunggu data masuk...")

# ============================================================
# 9. HALAMAN: SCAN & UPLOAD (MOBILE OPTIMIZED - NO TABS)
# ============================================================
elif menu == "📤 Scan & Upload":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    st.markdown("<h2 style='margin:0;'>INPUT DOKUMEN</h2>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Form Input
    nama_klien = st.text_input("🏢 Nama Perusahaan (Klien)")
    
    col_1, col_2 = st.columns(2)
    with col_1:
        divisi = st.selectbox("📂 Divisi", ["EXPORT", "IMPORT"])
    with col_2:
        kategori = st.selectbox("🏷️ Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Lainnya"])
    
    id_doc = st.text_input("🆔 No AWB / Invoice (Jika ada)")

    st.markdown("---")
    
    # INPUT AREA (Muncul berurutan agar pasti terlihat di HP)
    st.markdown("### 📥 Pilih Sumber Input")
    
    u_file = st.file_uploader("📁 Upload dari Galeri/File (PDF/Gambar)", type=["pdf", "jpg", "jpeg", "png"])
    
    st.markdown("<p style='text-align:center; color:#888;'>— ATAU —</p>", unsafe_allow_html=True)
    
    cam_file = st.camera_input("📷 Ambil Foto Dokumen")
    
    # Logika Penentuan File
    source_file = None
    is_pdf = False

    if u_file:
        source_file = u_file
        if u_file.type == "application/pdf":
            is_pdf = True
    elif cam_file:
        source_file = cam_file
        is_pdf = False

    # Tombol Eksekusi
    if source_file:
        if st.button("🚀 PROSES & SIMPAN KE DATABASE", type="primary"):
            if not nama_klien:
                st.warning("⚠️ Isi Nama Perusahaan dulu bray!")
            else:
                with st.spinner("AI sedang menganalisis dokumen..."):
                    content_to_process = source_file.read() if is_pdf else source_file
                    hasil = proses_analisis_ai(content_to_process, is_pdf)
                    
                    if "❌" not in hasil and sheet:
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([nama_klien, ts, id_doc if id_doc else "Auto", kategori, divisi, hasil])
                        st.success("✅ BERHASIL DISIMPAN!")
                        st.markdown(f"**Hasil AI:**\n\n{hasil}")
                    else:
                        st.error(hasil)

# ============================================================
# 10. HALAMAN: FULL DATABASE
# ============================================================
elif menu == "📑 Full Database":
    st.header("📑 Data Inventory Lengkap")
    if sheet:
        try:
            df_full = pd.DataFrame(sheet.get_all_records())
            if not df_full.empty:
                # Filter Cari
                cari = st.text_input("🔍 Cari Klien / No AWB")
                if cari:
                    df_full = df_full[df_full.astype(str).apply(lambda x: x.str.contains(cari, case=False)).any(axis=1)]
                
                st.dataframe(df_full, use_container_width=True)
                
                # Export CSV
                csv_data = df_full.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export ke Excel (CSV)", data=csv_data, file_name="ESP_Inventory.csv", mime="text/csv")
            else:
                st.warning("Belum ada data di database.")
        except Exception as e:
            st.error(f"Gagal memuat data: {e}")
