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
# 3. LOAD SEMUA API KEY (support 1 key atau multi-key)
# ============================================================
def load_api_keys():
    keys = []
    # Format lama — satu key
    if "GOOGLE_API_KEY" in st.secrets:
        keys.append(st.secrets["GOOGLE_API_KEY"])
    # Format baru — multi key: GOOGLE_API_KEY_1, _2, _3 ...
    for i in range(1, 10):
        k = f"GOOGLE_API_KEY_{i}"
        if k in st.secrets and st.secrets[k] not in keys:
            keys.append(st.secrets[k])
    return keys

API_KEYS = load_api_keys()

# Model valid per 2026 — gemini-1.5 sudah DEPRECATED/404
# Urutan: paling hemat quota → paling capable
MODEL_LIST = [
    "gemini-2.0-flash-lite",   # paling hemat, paling cepat
    "gemini-2.0-flash",        # standar, recommended
    "gemini-1.5-flash-8b",     # fallback ringan jika 2.0 bermasalah
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
        # Fix PEM key — TOML kadang simpan \n sebagai literal
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
    """Hash file untuk keperluan cache — hindari hit API dua kali."""
    file_input.seek(0)
    h = hashlib.md5(file_input.read()).hexdigest()
    file_input.seek(0)
    return h

def compress_image(file_input, max_size=(900, 900), quality=78):
    """Kompres gambar agar hemat token API."""
    img = Image.open(file_input)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf)

def build_content(file_input):
    """Siapkan payload konten untuk Gemini."""
    instruksi = (
        "Kamu adalah AI Inventory PT ESP. "
        "Ekstrak informasi penting dari dokumen ini: "
        "No AWB/Invoice, Nama Pengirim, Nama Penerima, "
        "deskripsi barang, berat, dan jumlah. "
        "Sajikan secara ringkas dan terstruktur."
    )
    if file_input.type == "application/pdf":
        file_input.seek(0)
        pdf_b64 = base64.standard_b64encode(file_input.read()).decode("utf-8")
        return [{"mime_type": "application/pdf", "data": pdf_b64}, instruksi]
    else:
        file_input.seek(0)
        return [compress_image(file_input), instruksi]

# ============================================================
# 6. FUNGSI ANALISIS AI — ROTASI KEY + ROTASI MODEL + CACHE
# ============================================================
def proses_analisis_ai(file_input):
    # Cache — file sama tidak perlu hit API ulang
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    if fhash in st.session_state.ai_cache:
        st.toast("⚡ Hasil dari cache — quota tidak terpakai.", icon="✅")
        return st.session_state.ai_cache[fhash]

    try:
        konten = build_content(file_input)
    except Exception as e:
        return f"❌ Gagal membaca file: {e}"

    # Rotasi: setiap KEY × setiap MODEL
    for key_idx, api_key in enumerate(API_KEYS):
        genai.configure(api_key=api_key)

        for model_name in MODEL_LIST:
            try:
                mdl = genai.GenerativeModel(model_name)
                response = mdl.generate_content(konten)
                hasil = response.text
                # Simpan ke cache
                st.session_state.ai_cache[fhash] = hasil
                return hasil

            except Exception as e:
                err = str(e)

                # 404 = model tidak ditemukan → lanjut model berikutnya
                if "404" in err or "not found" in err.lower():
                    continue

                # 429 / quota habis → lanjut key berikutnya (tidak perlu tunggu lama)
                if any(x in err for x in ["429", "quota", "RESOURCE_EXHAUSTED", "overload"]):
                    st.toast(
                        f"⚠️ Key-{key_idx+1} | {model_name} quota habis → ganti kombinasi",
                        icon="🔄"
                    )
                    break  # langsung ke key berikutnya

                # Error lain yang tidak dikenal → return langsung
                return f"❌ Error API: {e}"

    # Semua kombinasi habis
    return (
        "❌ Semua API Key dan model sudah dicoba — quota habis semua hari ini.\n\n"
        f"**Solusi:** Buat API Key baru gratis di aistudio.google.com dengan akun Google "
        f"berbeda, lalu tambahkan ke Secrets sebagai `GOOGLE_API_KEY_{len(API_KEYS)+1}`. "
        f"Quota reset setiap hari pukul 00.00 WIB."
    )

# ============================================================
# 7. SIDEBAR
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. ESP DATA INVENTORY")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Keys aktif: **{len(API_KEYS)} key**")
    st.caption("Build v7.0 - Production Ready")

# ============================================================
# 8. DASHBOARD
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 5])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=110)
    with col_text:
        st.markdown("""
            <div style='padding-top:8px;'>
                <h1 style='margin:0; color:#0e2135; font-size:2.4rem; font-weight:800;'>
                    PT. EKASARI PERKASA
                </h1>
                <p style='margin:0; color:#666; font-size:1.1rem;'>
                    Ini adalah Sistem Inventory Data PT. Ekasari Perkasa
                </p>
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
                with s1:
                    st.metric("Total Dokumen", f"{len(df)} Unit")
                with s2:
                    st.metric("Klien Terakhir", str(df[c_nama].iloc[-1]))
                with s3:
                    tgl_val = str(df[c_tgl].iloc[-1]).split(" ")[0] if c_tgl else "N/A"
                    st.metric("Aktivitas Terakhir", tgl_val)
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📑 Recent Activity Log")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.info("Dashboard siap! Belum ada data yang tercatat.")
        except Exception as e:
            st.error(f"Gagal memuat dashboard: {e}")
    else:
        st.warning("Koneksi Google Sheets belum aktif. Periksa konfigurasi Secrets.")

# ============================================================
# 9. SCAN & UPLOAD
# ============================================================
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
        u_pdf = st.file_uploader(
            "PDF", type=["pdf"],
            key="up_pdf", label_visibility="collapsed"
        )

    with col_img:
        st.markdown("##### 🖼️ Gambar / Foto")
        st.caption("Dari Galeri HP")
        u_img = st.file_uploader(
            "Gambar", type=["png", "jpg", "jpeg"],
            key="up_img", label_visibility="collapsed"
        )

    with col_cam:
        st.markdown("##### 📸 Kamera")
        st.caption("Foto langsung")
        if "cam" not in st.session_state:
            st.session_state.cam = False
        c_file = None
        if not st.session_state.cam:
            if st.button("📷 Buka Kamera", use_container_width=True):
                st.session_state.cam = True
                st.rerun()
        else:
            c_file = st.camera_input("Foto", label_visibility="collapsed")
            if st.button("❌ Tutup", use_container_width=True):
                st.session_state.cam = False
                st.rerun()

    # Tentukan file aktif — prioritas: Kamera > PDF > Gambar
    if st.session_state.cam and c_file is not None:
        file_aktif = c_file
    elif u_pdf is not None:
        file_aktif = u_pdf
    elif u_img is not None:
        file_aktif = u_img
    else:
        file_aktif = None

    # Preview
    if file_aktif:
        if hasattr(file_aktif, 'name') and file_aktif.name.lower().endswith(".pdf"):
            st.success(f"📄 File siap diproses: **{file_aktif.name}**")
        elif file_aktif is not c_file:
            try:
                file_aktif.seek(0)
                st.image(file_aktif, caption="Preview", use_column_width=True)
                file_aktif.seek(0)
            except Exception:
                pass

    if file_aktif:
        st.markdown("---")
        if st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
            if not nama_klien.strip():
                st.warning("⚠️ Nama Perusahaan wajib diisi!")
            else:
                with st.spinner("AI sedang menganalisis dokumen..."):
                    hasil = proses_analisis_ai(file_aktif)

                if "❌" in hasil:
                    st.error(hasil)
                else:
                    st.info(hasil)
                    if sheet:
                        try:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S")
                            ket = f"[DOKAP: {'YA' if kategori == 'DOKAP' else 'TIDAK'}] {hasil}"
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
                    data.to_csv(index=False),
                    "inventory_esp.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Belum ada data di database.")
        except Exception as e:
            st.error(f"Gagal memuat database: {e}")
    else:
        st.error("Koneksi ke Google Sheets gagal. Periksa konfigurasi Secrets.")
