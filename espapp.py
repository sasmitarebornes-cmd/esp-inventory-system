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
    # Gunakan 1.5 Flash sebagai default karena paling stabil untuk file di Free Tier
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
            # Membersihkan karakter escape agar kunci privat valid
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

# 5. FUNGSI ANALISIS AI (VERSI OPTIMAL FREE TIER)
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
    if model is None:
        return "Kesalahan Sistem: Model AI tidak terinisialisasi."

    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}

    file_hash = get_file_hash(file_input)
    if file_hash in st.session_state.ai_cache:
        st.toast("⚡ Hasil diambil dari cache.", icon="✅")
        return st.session_state.ai_cache[file_hash]

    instruksi = "Ekstrak teks penting dokumen ini. Fokus ke No AWB, Nama Pengirim/Penerima, dan rincian barang secara ringkas."

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
    except Exception as e:
        return f"Kesalahan membaca file: {e}"

    # Strategi Retry & Fallback
    MODELS_TO_TRY = ["gemini-1.5-flash", "gemini-1.5-flash-8b"]
    for m_name in MODELS_TO_TRY:
        try:
            curr_model = genai.GenerativeModel(m_name)
            for i in range(2): # 2x percobaan per model
                try:
                    response = curr_model.generate_content(konten)
                    st.session_state.ai_cache[file_hash] = response.text
                    return response.text
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        wait_time = 30 * (i + 1)
                        st.toast(f"⏳ Quota limit, nunggu {wait_time}s...", icon="⚠️")
                        time.sleep(wait_time)
                    else:
                        raise e
        except Exception:
            continue
            
    return "❌ Server Google overload. Mohon tunggu 1-2 menit sebelum mencoba lagi."

# 6. SIDEBAR
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. ESP DATA INVENTORY")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.caption("Build v6.3 - Optimized API")

# 7. DASHBOARD
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 4])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=120)
    with col_text:
        st.markdown("""
            <div style='padding-top: 10px;'>
                <h1 style='margin: 0; color: #0e2135; font-size: 2.8rem;'>PT. EKASARI PERKASA</h1>
                <p style='margin: 0; color: #666; font-size: 1.2rem;'>Logistics & Inventory Management System</p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                st.subheader("📊 Operational Statistics")
                s1, s2, s3 = st.columns(3)
                c_nama = 'Nama Perusahaan' if 'Nama Perusahaan' in df.columns else df.columns[0]
                c_tgl  = 'Tanggal' if 'Tanggal' in df.columns else None
                with s1: st.metric("Total Dokumen", f"{len(df)} Unit")
                with s2: st.metric("Klien Terakhir", str(df[c_nama].iloc[-1]))
                with s3: 
                    val_tgl = str(df[c_tgl].iloc[-1]).split(" ")[0] if c_tgl else "N/A"
                    st.metric("Aktivitas Terakhir", val_tgl)
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📑 Recent Activity Log")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.info("Belum ada data tercatat.")
        except Exception as e:
            st.error(f"Gagal memuat dashboard: {e}")

# 8. SCAN & UPLOAD
elif menu == "📤 Scan & Upload":
    st.header("📤 Input Dokumen Inventory")
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("Nama Perusahaan (Klien)", placeholder="Contoh: PT. Nama Klien")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with c_b:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Lainnya"])
        id_doc = st.text_input("ID Document", placeholder="No. AWB / Invoice")

    st.markdown("---")
    
    # Inject JS for Mobile File Support
    st.markdown("""<script>
        function patch() {
            const ins = document.querySelectorAll('input[type="file"]');
            ins.forEach(i => { i.setAttribute('accept', 'image/*,application/pdf,.pdf'); i.removeAttribute('capture'); });
        }
        patch(); new MutationObserver(patch).observe(document.body, {childList:true, subtree:true});
    </script>""", unsafe_allow_html=True)

    col_file, col_img, col_cam = st.columns(3)
    with col_file:
        u_pdf = st.file_uploader("📄 File PDF", type=["pdf"], key="u_pdf")
    with col_img:
        u_img = st.file_uploader("🖼️ Gambar", type=["png", "jpg", "jpeg"], key="u_img")
    with col_cam:
        if st.button("📸 Buka Kamera", use_container_width=True): st.session_state.cam = True
        c_file = st.camera_input("Foto", label_visibility="collapsed") if st.session_state.get('cam') else None

    file_aktif = c_file or u_pdf or u_img

    if file_aktif:
        if st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
            if not nama_klien:
                st.warning("⚠️ Nama Perusahaan wajib diisi!")
            else:
                with st.spinner("AI sedang memproses..."):
                    hasil = proses_analisis_ai(file_aktif)
                    if "❌" in hasil or "Kesalahan" in hasil:
                        st.error(hasil)
                    else:
                        st.info(hasil)
                        if sheet:
                            try:
                                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                                row = [nama_klien, ts, id_doc or file_aktif.name, kategori, divisi, hasil]
                                sheet.append_row(row)
                                st.success("✅ Data Berhasil Disimpan!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Gagal simpan: {e}")

# 9. FULL DATABASE
elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                st.dataframe(data, use_container_width=True)
                st.download_button("📥 Download CSV", data.to_csv(index=False), "inventory.csv", "text/csv")
            else: st.warning("Database kosong.")
        except Exception as e: st.error(f"Error: {e}")
