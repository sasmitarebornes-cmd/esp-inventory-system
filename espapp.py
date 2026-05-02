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
# 2. CSS CUSTOM (PREMIUM & MOBILE OPTIMIZED)
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
        sh = gc.open("DATA INVENTORY PT.ESP").sheet1
        return sh
    except Exception as e:
        st.sidebar.error(f"Koneksi Gagal: {e}")
        return None

sheet = init_gsheet()
API_KEYS = load_api_keys()

# ============================================================
# 4. AI AGENT ENGINE (DEEP ANALYSIS & COMPLETE EXTRACT)
# ============================================================
def analyze_document_deep(file_data, is_pdf=False, client_name=""):
    instruksi = f"""
    Kamu adalah AI AGENT EXPERT INVENTORY untuk PT. EKASARI PERKASA (PT. ESP).
    Dokumen ini milik Klien: {client_name}.
    
    Tugasmu adalah melakukan DEEP ANALYSIS:
    1. EKSTRAK DETAIL: Ambil No AWB/Invoice, Nama Pengirim & Penerima, Deskripsi Barang Lengkap, Berat (Gross/Net), dan Quantity/Koli.
    2. VALIDASI OPERASIONAL: Cek apakah ada data yang tidak sinkron atau mencurigakan.
    3. REKOMENDASI: Berikan kesimpulan singkat apakah dokumen ini lengkap untuk proses logistik selanjutnya.
    
    Format Output: Gunakan Markdown yang rapi dengan poin-poin profesional.
    """
    try:
        if not API_KEYS: return "❌ API Key tidak ditemukan bray."
        genai.configure(api_key=API_KEYS[0])
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        if is_pdf:
            content = [{"mime_type": "application/pdf", "data": file_data}, instruksi]
        else:
            img = Image.open(io.BytesIO(file_data) if isinstance(file_data, bytes) else file_data)
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
    if st.button("🔄 System Refresh"):
        st.cache_resource.clear()
        st.rerun()

# ============================================================
# 6. DASHBOARD (SINKRON DENGAN GAMBAR SHEETS)
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box"><h1>SMART DASHBOARD</h1><p>PT. ESP - Inventory Monitoring</p></div>', unsafe_allow_html=True)
    if sheet:
        raw_rows = sheet.get_all_records()
        if raw_rows:
            data = pd.DataFrame(raw_rows)
            # Menggunakan nama kolom sesuai gambar lo bray
            col_klien = "Nama Perusahaan"
            if col_klien in data.columns:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Dokumen", len(data))
                c2.metric("Klien Terdaftar", len(data[col_klien].unique()))
                c3.metric("Update", str(data.iloc[-1]['Tanggal']).split()[0])
                
                st.subheader("📊 Transaksi Terakhir")
                st.table(data.tail(5)[[col_klien, 'Kategori', 'Tanggal']])
        else:
            st.info("👋 Sistem Aktif. Silakan upload dokumen pertama lo bray!")

# ============================================================
# 7. SCAN & UPLOAD (FIXED HEADER & CAMERA)
# ============================================================
elif menu == "📤 Deep Scan & Upload":
    st.markdown('<div class="header-box"><h2>DEEP SCAN AGENT</h2><p>Auto-Folder & Deep Analysis</p></div>', unsafe_allow_html=True)
    
    # Input sesuai kolom Sheets
    nama_perusahaan = st.text_input("🏢 Nama Perusahaan (Klien)")
    c1, c2 = st.columns(2)
    with c1: divisi = st.selectbox("📂 divisi", ["EXPORT", "IMPORT"])
    with c2: kategori = st.selectbox("🏷️ Kategori", ["MAWB", "INVOICE", "PACKING LIST", "SURAT JALAN", "DOKAP"])
    id_doc = st.text_input("🆔 ID Document (AWB/INV)")

    st.markdown("---")
    u_file = st.file_uploader("📁 Upload File (PDF/Gambar)", type=["pdf", "jpg", "jpeg", "png"])
    
    if "cam_on" not in st.session_state: st.session_state.cam_on = False
    if st.button("📷 Aktifkan/Matikan Kamera"):
        st.session_state.cam_on = not st.session_state.cam_on
        st.rerun()
    
    cam_shot = None
    if st.session_state.cam_on:
        cam_shot = st.camera_input("Ambil Foto Dokumen")
        
    source = u_file if u_file else cam_shot

    if source and st.button("🚀 PROSES DOKUMEN SEKARANG", type="primary"):
        if not nama_perusahaan:
            st.error("⚠️ Nama Perusahaan wajib diisi buat Auto-Folder ya sayank!")
        else:
            with st.spinner("🤖 AI sedang bekerja keras..."):
                is_pdf = (getattr(source, 'type', '') == "application/pdf")
                content = source.read()
                
                # Eksekusi AI Deep Analysis
                keterangan_ai = analyze_document_deep(content, is_pdf, nama_perusahaan)
                
                if "❌" not in keterangan_ai:
                    tanggal_skrg = time.strftime("%Y-%m-%d %H:%M:%S")
                    # Urutan: Nama Perusahaan, Tanggal, ID Document, Kategori, divisi, Keterangan
                    sheet.append_row([
                        nama_perusahaan, 
                        tanggal_skrg, 
                        id_doc if id_doc else "Auto", 
                        kategori, 
                        divisi, 
                        keterangan_ai
                    ])
                    st.success(f"✅ Data {nama_perusahaan} Berhasil Disimpan!")
                    st.markdown(keterangan_ai)
                    st.session_state.cam_on = False
                else:
                    st.error(keterangan_ai)

# ============================================================
# 8. DATABASE (SINKRON DENGAN GAMBAR SHEETS)
# ============================================================
elif menu == "📑 Central Database":
    st.header("📑 Database Inventory ESP")
    if sheet:
        raw_rows = sheet.get_all_records()
        if raw_rows:
            df = pd.DataFrame(raw_rows)
            search = st.text_input("🔍 Cari (Nama Klien / No AWB)")
            if search:
                df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            st.dataframe(df, use_container_width=True)
            
            # Export
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Database CSV", csv, "Database_ESP.csv", "text/csv")
        else:
            st.warning("Database masih kosong ayank beib.")
