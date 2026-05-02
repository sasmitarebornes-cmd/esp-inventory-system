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
# 1. SETUP HALAMAN & IDENTITAS PT. ESP
# ============================================================
st.set_page_config(
    page_title="PT. ESP - AI AGENT INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS CUSTOM (STYLING PREMIUM & MOBILE FRIENDLY)
# ============================================================
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa !important; }
    [data-testid="stSidebar"] { background-color: #0e2135 !important; }
    [data-testid="stSidebar"] .stText, [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] .stMarkdown p { color: #ffffff !important; }
    
    .header-box {
        background: linear-gradient(90deg, #d32f2f 0%, #b71c1c 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        box-shadow: 0px 4px 20px rgba(0,0,0,0.2);
        margin-bottom: 25px;
    }
    .status-badge {
        background-color: #00e676;
        color: #000;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: bold;
    }
    .stButton button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        font-weight: bold;
        transition: 0.3s;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 3. KONEKSI GOOGLE SHEETS & API KEY
# ============================================================
def load_api_keys():
    return [st.secrets["GOOGLE_API_KEY"]] if "GOOGLE_API_KEY" in st.secrets else []

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
        st.sidebar.error(f"Koneksi Gagal: {e}")
        return None

sheet = init_gsheet()
API_KEYS = load_api_keys()

# ============================================================
# 4. AI AGENT ENGINE (DEEP ANALYSIS & AUTO-SORTING)
# ============================================================
def analyze_document_deep(file_data, is_pdf=False, client_name=""):
    """
    Fitur AI Agent: Menganalisa dokumen secara lengkap & mendalam.
    """
    instruksi = f"""
    Kamu adalah AI AGENT EXPERT INVENTORY untuk PT. EKASARI PERKASA (PT. ESP).
    Dokumen ini milik Klien: {client_name}.
    
    Tugasmu:
    1. ANALISA LENGKAP: Ekstrak No AWB, Invoice, Pengirim, Penerima, Deskripsi Barang Detail, Berat (Gross/Net), dan Koli/Quantity.
    2. VALIDASI DATA: Cek jika ada ketidaksamaan data atau hal mencurigakan dalam dokumen.
    3. AUTO-FOLDER LOGIC: Kelompokkan data ini ke dalam kategori operasional yang tepat.
    4. RINGKASAN EKSEKUTIF: Berikan insight apakah dokumen ini layak diproses atau ada kekurangan dokumen pendukung.
    
    Format Output: Gunakan Markdown yang sangat rapi dan profesional.
    """
    
    try:
        if not API_KEYS: return "❌ API Key tidak ditemukan."
        genai.configure(api_key=API_KEYS[0])
        model = genai.GenerativeModel("gemini-1.5-flash") # Versi stabil & cepat
        
        if is_pdf:
            content = [{"mime_type": "application/pdf", "data": file_data}, instruksi]
        else:
            img = Image.open(file_data)
            if img.mode != 'RGB': img = img.convert('RGB')
            content = [img, instruksi]
            
        response = model.generate_content(content)
        return response.text
    except Exception as e:
        return f"❌ Error AI: {str(e)}"

# ============================================================
# 5. SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=180)
    st.title("PT. ESP AGENT")
    st.markdown("<span class='status-badge'>AI CORE ACTIVE</span>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("MAIN MENU", ["🏠 Dashboard", "📤 Deep Scan & Upload", "📑 Central Database"])
    st.markdown("---")
    if st.button("🔄 System Reset"):
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# 6. DASHBOARD (INSIGHT & ANALYTICS)
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box"><h1>SMART DASHBOARD</h1><p>Monitoring Logistik & Inventory PT. ESP</p></div>', unsafe_allow_html=True)
    if sheet:
        data = pd.DataFrame(sheet.get_all_records())
        if not data.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Dokumen", len(data))
            c2.metric("Klien Terdaftar", len(data['Nama Klien'].unique()))
            c3.metric("Update Terakhir", data.iloc[-1]['Timestamp'].split()[0])
            st.subheader("📊 5 Transaksi Terakhir")
            st.table(data.tail(5)[['Nama Klien', 'Kategori', 'Divisi', 'Timestamp']])

# ============================================================
# 7. SCAN & UPLOAD (MODERN CAMERA TOGGLE)
# ============================================================
elif menu == "📤 Deep Scan & Upload":
    st.markdown('<div class="header-box"><h2>DEEP SCAN AGENT</h2><p>Analisis Otomatis & Penyimpanan Cloud</p></div>', unsafe_allow_html=True)
    
    klien = st.text_input("🏢 Nama Perusahaan Klien (Auto-Folder)")
    c1, c2 = st.columns(2)
    with c1: div = st.selectbox("📂 Divisi", ["EXPORT", "IMPORT"])
    with c2: kat = st.selectbox("🏷️ Jenis", ["MAWB", "INVOICE", "PACKING LIST", "SURAT JALAN", "DOKAP"])
    no_ref = st.text_input("🆔 Nomor Referensi (AWB/INV)")

    st.markdown("---")
    
    # Input Selection
    u_file = st.file_uploader("📁 Pilih Dokumen (PDF/Gambar)", type=["pdf", "jpg", "jpeg", "png"])
    
    st.markdown("<p style='text-align:center;'>— ATAU —</p>", unsafe_allow_html=True)
    
    if "cam_on" not in st.session_state: st.session_state.cam_on = False
    
    if not st.session_state.cam_on:
        if st.button("📷 Buka Kamera Scan"):
            st.session_state.cam_on = True
            st.rerun()
    else:
        cam_shot = st.camera_input("Ambil Foto Dokumen")
        if st.button("❌ Tutup Kamera"):
            st.session_state.cam_on = False
            st.rerun()
        
    source = u_file if u_file else (cam_shot if st.session_state.cam_on else None)

    if source and st.button("🚀 JALANKAN AI ANALISIS", type="primary"):
        if not klien:
            st.error("⚠️ Nama Klien harus diisi bray!")
        else:
            with st.spinner("🤖 AI Agent sedang membedah dokumen..."):
                is_pdf = (getattr(source, 'type', '') == "application/pdf")
                raw_data = source.read() if is_pdf else source
                
                hasil_analisis = analyze_document_deep(raw_data, is_pdf, klien)
                
                if "❌" not in hasil_analisis:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    # Simpan ke Database Sheets
                    sheet.append_row([klien, ts, no_ref if no_ref else "Auto", kat, div, hasil_analisis])
                    st.success(f"✅ Dokumen {klien} Berhasil Dianalisa & Disimpan!")
                    st.markdown(hasil_analisis)
                    st.session_state.cam_on = False
                else:
                    st.error(hasil_analisis)

# ============================================================
# 8. DATABASE (FILTER & SEARCH)
# ============================================================
elif menu == "📑 Central Database":
    st.header("📊 Database Logistik Terpusat")
    if sheet:
        df = pd.DataFrame(sheet.get_all_records())
        search = st.text_input("🔍 Cari Klien, Nomor AWB, atau Hasil Analisis")
        if search:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Database", csv, "Database_ESP.csv", "text/csv")
    
