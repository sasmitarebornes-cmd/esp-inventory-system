import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from PIL import Image
import os
import time
import pandas as pd
import base64
import hashlib
import io

# 1. SETUP HALAMAN
st.set_page_config(
    page_title="PT. ESP - SMART INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# 2. CSS OVERRIDE
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

# 3. INISIALISASI GEMINI API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error(f"Gagal Inisialisasi API: {e}")
    model = None

# 4. KONEKSI GOOGLE SHEETS
@st.cache_resource
def init_gsheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open("DATA INVENTORY PT.ESP").sheet1
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Sheets: {e}")
        return None

sheet = init_gsheet()

# 5. FUNGSI ANALISIS AI (OPTIMIZED FOR PAID TIER)
def get_file_hash(file_input):
    file_input.seek(0)
    content = file_input.read()
    file_input.seek(0)
    return hashlib.md5(content).hexdigest()

def compress_image(file_input, max_size=(1024, 1024), quality=80):
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf)

def proses_analisis_ai(file_input):
    if model is None: return "Kesalahan Sistem: Model AI tidak terinisialisasi."
    if "ai_cache" not in st.session_state: st.session_state.ai_cache = {}
    
    file_hash = get_file_hash(file_input)
    if file_hash in st.session_state.ai_cache:
        st.toast("⚡ Hasil diambil dari cache.", icon="✅")
        return st.session_state.ai_cache[file_hash]

    instruksi = "Ekstrak teks penting: No AWB, Nama Pengirim/Penerima, dan rincian barang secara ringkas."

    try:
        if file_input.type == "application/pdf":
            file_input.seek(0)
            pdf_bytes = file_input.read()
            pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
            konten = [{'mime_type': 'application/pdf', 'data': pdf_b64}, instruksi]
        else:
            file_input.seek(0)
            img_compressed = compress_image(file_input)
            konten = [img_compressed, instruksi]
    except Exception as e: return f"Kesalahan membaca file: {e}"

    # REVISI: JALUR PRIORITAS (PAID TIER)
    for i in range(3):
        try:
            response = model.generate_content(konten)
            st.session_state.ai_cache[file_hash] = response.text
            return response.text
        except Exception as e:
            err_msg = str(e).lower()
            if any(x in err_msg for x in ["429", "quota", "overloaded"]):
                # Waktu tunggu dipangkas dari 45 detik menjadi 2-5 detik untuk jalur berbayar
                wait_time = 2 * (i + 1)
                st.warning(f"🚀 Menghubungi Jalur Prioritas Google... ({i+1}/3)")
                time.sleep(wait_time)
            else:
                return f"❌ Error API: {e}"
            
    return "❌ Server masih sibuk. Klik 'PROSES & SIMPAN' lagi bray."

# 6. SIDEBAR
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. ESP DATA INVENTORY")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.caption("Build v6.5 - Premium Paid Tier")

# 7. DASHBOARD
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 4])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"): st.image("ESP LOGO ICON RED WHITE.png", width=120)
    with col_text:
        st.markdown("<h1 style='margin: 0; color: #0e2135;'>PT. EKASARI PERKASA</h1><p>Logistics & Inventory System</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Dokumen", f"{len(df)} Unit")
                s2.metric("Klien Terakhir", str(df.iloc[-1, 0]))
                s3.metric("Update Terakhir", str(df.iloc[-1, 1]).split(" ")[0])
                st.dataframe(df.tail(10), use_container_width=True)
        except: pass

# 8. SCAN & UPLOAD
elif menu == "📤 Scan & Upload":
    st.header("📤 Input Dokumen Inventory")
    c_a, c_b = st.columns(2)
    nama_klien = c_a.text_input("Nama Perusahaan (Klien)")
    divisi = c_a.selectbox("Divisi", ["EXPORT", "IMPORT"])
    kategori = c_b.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Lainnya"])
    id_doc = c_b.text_input("ID Document")

    col_file, col_img, col_cam = st.columns(3)
    u_pdf = col_file.file_uploader("📄 PDF", type=["pdf"])
    u_img = col_img.file_uploader("🖼️ Gambar", type=["png", "jpg", "jpeg"])
    if col_cam.button("📸 Kamera", use_container_width=True): st.session_state.cam = True
    c_file = st.camera_input("Cam", label_visibility="collapsed") if st.session_state.get('cam') else None

    file_aktif = c_file or u_pdf or u_img
    if file_aktif and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien: st.warning("⚠️ Isi Nama Perusahaan!")
        else:
            with st.spinner("AI sedang memproses dokumen..."):
                hasil = proses_analisis_ai(file_aktif)
                if "❌" in hasil: st.error(hasil)
                else:
                    st.info(hasil)
                    if sheet:
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([nama_klien, ts, id_doc or file_aktif.name, kategori, divisi, hasil])
                        st.success("✅ Data Berhasil Disimpan ke Google Sheets!")
                        time.sleep(0.5)
                        st.rerun()

# 9. FULL DATABASE
elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            st.dataframe(data, use_container_width=True)
            st.download_button("📥 Download CSV", data.to_csv(index=False), "inventory.csv", "text/csv")
        except: st.error("Gagal muat data.")
