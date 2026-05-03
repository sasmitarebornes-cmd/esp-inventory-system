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

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. EKASARI PERKASA - SMART INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS CUSTOM
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
# 3. LOAD API KEYS
# ============================================================
def load_api_keys():
    keys = []
    if "GOOGLE_API_KEY" in st.secrets:
        keys.append(st.secrets["GOOGLE_API_KEY"])
    for i in range(1, 10):
        k = f"GOOGLE_API_KEY_{i}"
        if k in st.secrets and st.secrets[k] not in keys:
            keys.append(st.secrets[k])
    return keys

API_KEYS = load_api_keys()

# FIX: Model yang valid per 2026 — gemini-3 belum ada, gemini-2.0-flash adalah yang terbaru
MODEL_LIST = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash-8b"]

if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY di Streamlit Secrets!")
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
        return gc.open("DATA INVENTORY PT.ESP").get_worksheet(0)
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

def compress_image(file_input, max_size=(900, 900), quality=78):
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf)

def build_content(file_input, instruksi):
    """Siapkan payload untuk Gemini — PDF pakai base64, gambar dikompres."""
    is_pdf = hasattr(file_input, 'type') and file_input.type == "application/pdf"
    is_pdf = is_pdf or (hasattr(file_input, 'name') and str(file_input.name).lower().endswith('.pdf'))

    if is_pdf:
        # FIX: PDF harus base64, bukan raw bytes
        file_input.seek(0)
        pdf_b64 = base64.standard_b64encode(file_input.read()).decode("utf-8")
        return [{"mime_type": "application/pdf", "data": pdf_b64}, instruksi]
    else:
        file_input.seek(0)
        return [compress_image(file_input), instruksi]

# ============================================================
# 6. FUNGSI ANALISIS AI — ROTASI KEY + MODEL + CACHE
# ============================================================
def proses_analisis_ai(file_input, client_name=""):
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    if fhash in st.session_state.ai_cache:
        st.toast("⚡ Hasil dari cache — quota tidak terpakai.", icon="✅")
        return st.session_state.ai_cache[fhash]

    instruksi = (
        f"Kamu adalah AI Inventory PT EKASARI PERKASA. "
        f"Analisis dokumen klien {client_name}. "
        f"Ekstrak: No AWB/Invoice, Nama Pengirim, Nama Penerima, "
        f"deskripsi barang, berat, jumlah. Sajikan ringkas dan terstruktur."
    )

    try:
        konten = build_content(file_input, instruksi)
    except Exception as e:
        return f"❌ Gagal membaca file: {e}"

    for key_idx, api_key in enumerate(API_KEYS):
        genai.configure(api_key=api_key)
        for model_name in MODEL_LIST:
            try:
                mdl = genai.GenerativeModel(model_name)
                response = mdl.generate_content(konten)
                hasil = response.text
                st.session_state.ai_cache[fhash] = hasil
                return hasil
            except Exception as e:
                err = str(e)
                if "404" in err or "not found" in err.lower():
                    continue
                if any(x in err for x in ["429", "quota", "RESOURCE_EXHAUSTED"]):
                    st.toast(f"⚠️ Key-{key_idx+1} | {model_name} quota habis → ganti", icon="🔄")
                    break
                return f"❌ Error API: {e}"

    return (
        "❌ Semua API Key quota habis.\n\n"
        "Tambahkan key baru di Streamlit Secrets sebagai "
        f"GOOGLE_API_KEY_{len(API_KEYS)+1} dari aistudio.google.com"
    )

# ============================================================
# 7. SIDEBAR
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
    st.caption(f"🔑 API Keys: {len(API_KEYS)} aktif")
    st.caption("Build v7.1 - Stable")
    if st.button("🔄 System Refresh"):
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# 8. DASHBOARD
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    c_logo, c_txt = st.columns([1, 5])
    with c_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=100)
    with c_txt:
        st.markdown("""
            <div style='padding-top:8px;'>
                <h1 style='margin:0; color:#0e2135;'>PT. EKASARI PERKASA</h1>
                <p style='margin:0; color:#666;'>Ini adalah Sistem Inventory Data PT. Ekasari Perkasa</p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                c_nama = 'Nama Perusahaan' if 'Nama Perusahaan' in df.columns else df.columns[0]
                c_tgl  = 'Tanggal' if 'Tanggal' in df.columns else None
                with s1:
                    st.metric("Total Dokumen", f"{len(df)} Unit")
                with s2:
                    st.metric("Klien Terakhir", str(df[c_nama].iloc[-1]))
                with s3:
                    tgl_val = str(df[c_tgl].iloc[-1]).split(" ")[0] if c_tgl else "N/A"
                    st.metric("Aktivitas Terakhir", tgl_val)
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📊 Transaksi Terbaru")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.info("👋 Selamat datang! Belum ada data yang tercatat.")
        except Exception as e:
            st.error(f"Gagal memuat dashboard: {e}")
    else:
        st.warning("Koneksi Google Sheets belum aktif.")

# ============================================================
# 9. SCAN & UPLOAD
# ============================================================
elif menu == "📤 Scan & Upload":
    st.header("📤 Input Dokumen Inventory")

    col1, col2 = st.columns(2)
    with col1:
        nama_klien = st.text_input("Nama Perusahaan (Klien)", placeholder="Contoh: PT. Nama Klien")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with col2:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB" , "PIB", "Sewa Gudang" , "Lainnya"])
        id_doc = st.text_input("ID Document (No AWB/Invoice)")

    st.markdown("---")

    # JS: paksa browser HP tampilkan ikon File Manager
    st.markdown("""
        <script>
        function patchFileInputs() {
            document.querySelectorAll('input[type="file"]').forEach(function(el) {
                el.setAttribute('accept', 'image/*,application/pdf,.pdf,.PDF');
                el.removeAttribute('capture');
            });
        }
        patchFileInputs();
        new MutationObserver(patchFileInputs).observe(document.body, {childList:true, subtree:true});
        </script>
    """, unsafe_allow_html=True)

    col_file, col_img, col_cam = st.columns(3)

    with col_file:
        st.markdown("##### 📄 File / PDF")
        st.caption("Dari File Manager HP")
        u_pdf = st.file_uploader("PDF", type=["pdf"], key="up_pdf", label_visibility="collapsed")

    with col_img:
        st.markdown("##### 🖼️ Gambar / Foto")
        st.caption("Dari Galeri HP")
        u_img = st.file_uploader("Gambar", type=["png", "jpg", "jpeg"], key="up_img", label_visibility="collapsed")

    with col_cam:
        st.markdown("##### 📸 Kamera")
        st.caption("Foto langsung")
        if "cam_on" not in st.session_state:
            st.session_state.cam_on = False
        c_file = None
        if st.button("📷 Buka/Tutup Kamera", use_container_width=True):
            st.session_state.cam_on = not st.session_state.cam_on
            st.rerun()
        if st.session_state.cam_on:
            c_file = st.camera_input("Foto", label_visibility="collapsed")

    # Tentukan file aktif
    if st.session_state.cam_on and c_file is not None:
        file_aktif = c_file
    elif u_pdf is not None:
        file_aktif = u_pdf
    elif u_img is not None:
        file_aktif = u_img
    else:
        file_aktif = None

    # Preview
    if file_aktif:
        if hasattr(file_aktif, 'name') and str(file_aktif.name).lower().endswith(".pdf"):
            st.success(f"📄 File siap diproses: **{file_aktif.name}**")
        else:
            try:
                file_aktif.seek(0)
                st.image(file_aktif, caption="Preview", use_column_width=True)
                file_aktif.seek(0)
            except Exception:
                pass

    if file_aktif:
        st.markdown("---")
        if st.button("🚀 PROSES & SIMPAN", type="primary", use_container_width=True):
            if not nama_klien.strip():
                st.warning("⚠️ Nama Perusahaan wajib diisi!")
            else:
                with st.spinner("🤖 AI sedang menganalisis dokumen..."):
                    hasil_ai = proses_analisis_ai(file_aktif, nama_klien)

                if "❌" in hasil_ai:
                    st.error(hasil_ai)
                else:
                    st.info(f"📄 Hasil Analisis:\n{hasil_ai}")
                    if sheet:
                        try:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S")
                            ket = f"[DOKAP: {'YA' if kategori == 'DOKAP' else 'TIDAK'}] {hasil_ai}"
                            sheet.append_row([
                                nama_klien, ts,
                                id_doc if id_doc else file_aktif.name,
                                kategori, divisi, ket
                            ])
                            st.success(f"✅ Data {divisi} berhasil disimpan ke Google Sheets!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal simpan ke Google Sheets: {e}")
                    else:
                        st.warning("Google Sheets tidak terhubung.")

# ============================================================
# 10. FULL DATABASE
# ============================================================
elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                st.dataframe(data, use_container_width=True)
                st.download_button(
                    "📥 Download CSV",
                    data.to_csv(index=False).encode('utf-8'),
                    "Database_ESP.csv",
                    "text/csv"
                )
            else:
                st.warning("Belum ada data di database.")
        except Exception as e:
            st.error(f"Gagal memuat database: {e}")
    else:
        st.error("Koneksi ke Google Sheets gagal.")
