import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from PIL import Image
import os
import time
import pandas as pd
import base64

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
# Urutan model: coba yang paling hemat quota dulu, fallback ke yang lain
MODEL_LIST = ["gemini-2.0-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash-8b"]

model = None
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel(MODEL_LIST[0])  # mulai dari model paling hemat
except Exception as e:
    st.error(f"Gagal Inisialisasi API: {e}")

# 4. KONEKSI GOOGLE SHEETS
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

# 5. FUNGSI ANALISIS AI — dengan AUTO RETRY & MODEL FALLBACK
def proses_analisis_ai(file_input):
    if model is None:
        return "Kesalahan Sistem: Model AI tidak terinisialisasi."

    instruksi = "Kamu adalah AI Inventory PT ESP. Ekstrak teks penting dari dokumen ini secara detail."

    # Siapkan konten berdasarkan tipe file
    try:
        if file_input.type == "application/pdf":
            pdf_bytes = file_input.read()
            pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
            konten = [{'mime_type': 'application/pdf', 'data': pdf_b64}, instruksi]
        else:
            img = Image.open(file_input)
            konten = [img, instruksi]
    except Exception as e:
        return f"Kesalahan membaca file: {e}"

    # AUTO RETRY: coba hingga 3x dengan jeda bertahap, lalu fallback model
    for model_name in MODEL_LIST:
        current_model = genai.GenerativeModel(model_name)
        for percobaan in range(1, 4):  # 3x percobaan per model
            try:
                response = current_model.generate_content(konten)
                return response.text  # sukses, langsung return
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower() or "resource" in err_str.lower():
                    # Kuota habis — tunggu lalu coba lagi
                    jeda = percobaan * 15  # 15s, 30s, 45s
                    st.toast(f"⏳ Kuota penuh, mencoba ulang dalam {jeda} detik... (Model: {model_name}, percobaan {percobaan}/3)", icon="⚠️")
                    time.sleep(jeda)
                else:
                    # Error lain, langsung gagal
                    return f"Kesalahan Sistem: {e}"

        # Semua percobaan di model ini gagal, coba model berikutnya
        st.toast(f"🔄 Beralih ke model cadangan...", icon="🔁")
        time.sleep(5)

    return "❌ Semua model AI sedang overload. Coba lagi dalam 2-3 menit, atau upgrade ke Gemini API berbayar."

# 6. SIDEBAR
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. ESP DATA INVENTORY")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.caption("Build v6.1 - Auto Retry + Fallback Model")

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
                <p style='margin: 0; color: #666; font-size: 1.2rem;'>
                    Ini adalah Sistem Inventory Data PT. Ekasari Perkasa
                </p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if sheet:
        try:
            raw_data = sheet.get_all_records()
            df = pd.DataFrame(raw_data)
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
                    val_tgl = str(df[c_tgl].iloc[-1]).split(" ")[0] if c_tgl else "N/A"
                    st.metric("Aktivitas Terakhir", val_tgl)
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("📑 Recent Activity Log")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.info("Dashboard siap! Belum ada data yang tercatat.")
        except Exception as e:
            st.error(f"Gagal memuat dashboard: {e}")
    else:
        st.warning("Koneksi Google Sheets belum aktif. Periksa konfigurasi Secrets.")

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

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📁 Upload File")
        u_file = st.file_uploader("Pilih PDF/Gambar", type=["pdf", "png", "jpg", "jpeg"])
    with col_r:
        st.subheader("📸 Scan Kamera")
        if "cam" not in st.session_state:
            st.session_state.cam = False

        c_file = None
        if not st.session_state.cam:
            if st.button("📷 Buka Kamera", use_container_width=True):
                st.session_state.cam = True
                st.rerun()
        else:
            c_file = st.camera_input("Ambil Foto")
            if st.button("❌ Tutup Kamera"):
                st.session_state.cam = False
                st.rerun()

    if st.session_state.cam and c_file is not None:
        file_aktif = c_file
    elif u_file is not None:
        file_aktif = u_file
    else:
        file_aktif = None

    if file_aktif:
        if st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
            if not nama_klien:
                st.warning("⚠️ Nama Perusahaan wajib diisi!")
            else:
                with st.spinner("AI sedang menganalisis dokumen... (mungkin perlu beberapa saat jika kuota penuh)"):
                    hasil = proses_analisis_ai(file_aktif)
                    if "Kesalahan" in hasil or "❌" in hasil:
                        st.error(hasil)
                    else:
                        st.info(hasil)
                        if sheet:
                            try:
                                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                                ket_final = f"[DOKAP: {'YA' if kategori == 'DOKAP' else 'TIDAK'}] - {hasil}"
                                row = [nama_klien, ts, id_doc if id_doc else file_aktif.name, kategori, divisi, ket_final]
                                sheet.append_row(row)
                                st.success(f"✅ Data {divisi} Berhasil Disimpan!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal simpan ke Google Sheet: {e}")
                        else:
                            st.warning("Google Sheets tidak terhubung, data tidak tersimpan.")

# 9. FULL DATABASE
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
