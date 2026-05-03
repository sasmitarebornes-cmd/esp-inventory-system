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
import mimetypes
import json
from datetime import datetime, timedelta

# 🔹 Firebase Storage import
try:
    import firebase_admin
    from firebase_admin import credentials, storage
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# ============================================================
# 1. SETUP HALAMAN
# ============================================================
st.set_page_config(
    page_title="PT. ESP - SMART INVENTORY",
    layout="wide",
    page_icon="ESP LOGO ICON RED WHITE.png"
)

# ============================================================
# 2. CSS OVERRIDE - PREMIUM DESIGN
# ============================================================
st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');
    
    /* Root Variables */
    :root {
        --primary-navy: #1e3a5f;
        --secondary-navy: #2d4a6f;
        --accent-gold: #f59e0b;
        --accent-gold-hover: #d97706;
        --bg-gradient-start: #f8fafc;
        --bg-gradient-end: #e0e7ff;
        --card-bg: rgba(255, 255, 255, 0.95);
        --text-primary: #1e293b;
        --text-secondary: #64748b;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
    /* Animated Background Gradient */
    .stApp {
        background: linear-gradient(-45deg, #f8fafc, #e0e7ff, #f0f9ff, #f8fafc);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
        font-family: 'Inter', sans-serif !important;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Sidebar Premium Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
        box-shadow: 4px 0 15px rgba(0, 0, 0, 0.1);
    }
    
    [data-testid="stSidebar"] .stText,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] h1 {
        color: #f1f5f9 !important;
    }
    
    /* Glassmorphism Cards */
    .header-box {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        padding: 40px 60px;
        border-radius: 20px;
        box-shadow: var(--shadow-xl);
        margin-bottom: 40px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-left: 6px solid var(--accent-gold);
        position: relative;
        overflow: hidden;
    }
    
    .header-box::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, transparent 100%);
        pointer-events: none;
    }
    
    /* Metric Cards Premium */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.95) 100%) !important;
        padding: 30px !important;
        border-radius: 16px !important;
        box-shadow: var(--shadow-lg) !important;
        border: 1px solid rgba(226, 232, 240, 0.8) !important;
        border-left: 5px solid var(--accent-gold) !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-xl) !important;
    }
    
    /* Title Styling */
    .header-box h1 {
        font-family: 'Playfair Display', serif !important;
        color: var(--primary-navy) !important;
        font-weight: 700;
        font-size: 2.5em;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    .header-box p {
        color: var(--text-secondary) !important;
        font-size: 1.1em;
        margin: 10px 0 0 0;
        font-weight: 400;
    }
    
    /* Warning/Error/Success Boxes Premium */
    .warning-box {
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(251, 191, 36, 0.05) 100%);
        border-left: 5px solid #f59e0b;
        padding: 20px;
        border-radius: 12px;
        margin: 15px 0;
        box-shadow: var(--shadow-md);
    }
    
    .error-box {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
        border-left: 5px solid #ef4444;
        padding: 20px;
        border-radius: 12px;
        margin: 15px 0;
        box-shadow: var(--shadow-md);
    }
    
    .success-box {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
        border-left: 5px solid #22c55e;
        padding: 20px;
        border-radius: 12px;
        margin: 15px 0;
        box-shadow: var(--shadow-md);
    }
    
    /* Title Logo Container */
    .title-logo {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 30px;
        padding: 20px;
        background: rgba(255, 255, 255, 0.9);
        border-radius: 16px;
        box-shadow: var(--shadow-md);
    }
    
    /* Signature Premium */
    .signature-box {
        text-align: center;
        margin-top: 60px;
        padding: 30px;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 250, 252, 0.9) 100%);
        border-radius: 16px;
        box-shadow: var(--shadow-md);
        border: 1px solid rgba(226, 232, 240, 0.8);
    }
    
    .signature-text {
        font-family: 'Playfair Display', 'Brush Script MT', cursive;
        font-size: 32px;
        background: linear-gradient(135deg, var(--primary-navy) 0%, var(--accent-gold) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    
    .signature-year {
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        color: var(--text-secondary);
        font-weight: 500;
    }
    
    /* Button Styling */
    .stButton>button {
        background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-gold-hover) 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        box-shadow: var(--shadow-md) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg) !important;
    }
    
    /* Input Fields */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>select {
        border-radius: 10px !important;
        border: 2px solid #e2e8f0 !important;
        padding: 10px 15px !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput>div>div>input:focus,
    .stSelectbox>div>div>select:focus {
        border-color: var(--accent-gold) !important;
        box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1) !important;
    }
    
    /* Radio Buttons */
    div[data-testid="stRadio"] > label {
        background: rgba(255, 255, 255, 0.9);
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: var(--shadow-sm);
        margin: 5px 0;
    }
    
    /* Checkbox */
    .stCheckbox>div>div>label {
        background: rgba(255, 255, 255, 0.9);
        padding: 12px 18px;
        border-radius: 10px;
        box-shadow: var(--shadow-sm);
    }
    
    /* Table Styling */
    div[data-testid="stTable"] {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }
    
    /* Expander Premium */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 10px;
        padding: 15px;
    }
    
    /* Scrollbar Custom */
    ::-webkit-scrollbar {
        width: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, var(--accent-gold) 0%, var(--accent-gold-hover) 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent-gold-hover);
    }
    
    /* Divider */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--accent-gold), transparent);
        margin: 30px 0;
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

MODEL_LIST = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp",
    "gemini-3-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-pro"
]

if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY ditemukan!")
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
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        
        spreadsheet = gc.open("DATA INVENTORY PT.ESP")
        worksheet = spreadsheet.sheet1
        
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) == 0:
            header = ["Nama Perusahaan", "Timestamp", "ID Dokumen", "Kategori", "Divisi", "Hasil Analisis"]
            worksheet.append_row(header)
            st.sidebar.warning("⚠️ Sheet kosong, header default dibuat")
        
        return worksheet
        
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f" Sheets API Error: {str(e)}")
        st.sidebar.info("💡 Pastikan spreadsheet 'DATA INVENTORY PT.ESP' sudah di-share")
        return None
    except Exception as e:
        st.sidebar.error(f" Sheets Error: {type(e).__name__}: {str(e)}")
        return None

sheet = init_gsheet()

# ============================================================
# 5. FIREBASE STORAGE INITIALIZATION
# ============================================================
@st.cache_resource
def init_firebase():
    if not FIREBASE_AVAILABLE:
        return None
    try:
        if not firebase_admin._apps:
            firebase_config = st.secrets.get("firebase_config", {})
            if not firebase_config:
                raise ValueError("firebase_config not found")
            
            sa_json = firebase_config.get("service_account", {})
            
            if isinstance(sa_json, str):
                try:
                    sa_json = json.loads(sa_json)
                except:
                    sa_json = eval(sa_json)
            elif not isinstance(sa_json, dict):
                sa_json = dict(sa_json)
            
            if 'private_key' not in sa_json:
                raise ValueError("private_key missing")
            
            cred = credentials.Certificate(sa_json)
            storage_bucket = firebase_config.get("storage_bucket")
            
            if not storage_bucket:
                raise ValueError("storage_bucket missing")
            
            firebase_admin.initialize_app(cred, {
                'storageBucket': storage_bucket
            })
        return storage.bucket()
    except Exception as e:
        st.sidebar.error(f" Firebase Error: {str(e)}")
        return None

firebase_bucket = init_firebase()

# ============================================================
# 6-11. HELPER FUNCTIONS (Tidak Berubah)
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
    return buf

def build_content(file_input):
    instruksi = "Kamu adalah AI Inventory PT ESP. Ekstrak informasi penting dari dokumen ini."
    if file_input.type == "application/pdf":
        file_input.seek(0)
        pdf_data = file_input.read()
        return [{"mime_type": "application/pdf", "data": pdf_data}, instruksi]
    else:
        buf = compress_image(file_input)
        return [Image.open(buf), instruksi]

def validate_document_fields(file_input, user_company, user_divisi, user_kategori, user_id_doc):
    try:
        file_input.seek(0)
        validation_prompt = """
Analisis dokumen dan ekstrak dalam JSON:
{
  "company_name": "Nama perusahaan",
  "divisi": "EXPORT atau IMPORT",
  "document_type": "MAWB/Invoice/Surat Jalan/DOKAP/Perizinan/PEB/PIB/SPPB/Lainnya",
  "document_id": "Nomor dokumen",
  "confidence": "HIGH atau LOW"
}
Output HANYA JSON.
"""
        if file_input.type == "application/pdf":
            file_input.seek(0)
            pdf_data = file_input.read()
            konten = [{"mime_type": "application/pdf", "data": pdf_data}, validation_prompt]
        else:
            file_input.seek(0)
            img = Image.open(file_input)
            konten = [img, validation_prompt]
        
        extracted = None
        for api_key in API_KEYS:
            genai.configure(api_key=api_key)
            for model_name in MODEL_LIST:
                try:
                    mdl = genai.GenerativeModel(model_name)
                    response = mdl.generate_content(konten)
                    hasil = response.text.strip()
                    if "```json" in hasil:
                        hasil = hasil.split("```json")[1].split("```")[0].strip()
                    elif "```" in hasil:
                        hasil = hasil.split("```")[1].strip()
                    extracted = json.loads(hasil)
                    break
                except Exception as e:
                    if "404" in str(e).lower():
                        continue
                    raise
            if extracted: break
            
        if not extracted:
            raise ValueError("AI gagal return JSON")
            
        validation_result = {
            "extracted": extracted,
            "mismatches": [],
            "can_proceed": True,
            "warnings": []
        }
        
        if extracted.get("company_name") and extracted["company_name"] not in [None, "null"]:
            doc_company = extracted["company_name"].upper()
            user_company_clean = user_company.upper().strip()
            if user_company_clean and doc_company not in user_company_clean and user_company_clean not in doc_company:
                validation_result["warnings"].append(f"⚠️ Nama di dokumen: \"{extracted['company_name']}\"")
        
        if extracted.get("divisi") in ["EXPORT", "IMPORT"]:
            if extracted["divisi"] != user_divisi:
                validation_result["mismatches"].append({
                    "field": "Divisi", "user_input": user_divisi, 
                    "detected": extracted["divisi"], "severity": "ERROR"
                })
                validation_result["can_proceed"] = False
                
        valid_cats = ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "Lainnya"]
        if extracted.get("document_type") in valid_cats:
            if extracted["document_type"] != user_kategori:
                validation_result["mismatches"].append({
                    "field": "Kategori", "user_input": user_kategori, 
                    "detected": extracted["document_type"], "severity": "ERROR"
                })
                validation_result["can_proceed"] = False
                
        if extracted.get("document_id") and extracted["document_id"] not in [None, "null"]:
            user_id_clean = user_id_doc.strip() if user_id_doc else ""
            if user_id_clean and extracted["document_id"].strip().upper() != user_id_clean.upper():
                validation_result["warnings"].append(f"⚠️ ID terdeteksi: \"{extracted['document_id']}\"")
                
        return validation_result
    except Exception as e:
        return {
            "extracted": {"error": str(e)},
            "mismatches": [],
            "can_proceed": True,
            "warnings": [f"⚠️ Validasi gagal: {str(e)}"]
        }

def upload_to_firebase(file_input, company_name, category, doc_id=None):
    if not FIREBASE_AVAILABLE:
        return None, " Library belum terinstall"
    bucket = firebase_bucket
    if not bucket:
        return None, " Firebase tidak terinisialisasi"
    try:
        file_input.seek(0)
        file_bytes = file_input.read()
        filename = file_input.name or f"DOC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        now = datetime.now()
        folder_path = f"{company_name.strip()}/{now.year}/{now.strftime('%Y-%m-%d')}/{category}"
        blob_path = f"{folder_path}/{doc_id}_{filename}" if doc_id else f"{folder_path}/{filename}"
        
        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_bytes, content_type=file_input.type or "application/octet-stream")
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=604800),
            method="GET"
        )
        return signed_url, None
    except Exception as e:
        return None, f" Upload Error: {str(e)}"

def proses_analisis_ai(file_input):
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    if fhash in st.session_state.ai_cache:
        return st.session_state.ai_cache[fhash]
    try:
        konten = build_content(file_input)
    except Exception as e:
        return f"❌ Gagal baca file: {e}"
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
                if "404" in err or "not found" in err:
                    continue
                if "quota" in err:
                    continue
                return f"❌ Error API: {e}"
    return "❌ Gagal."

# ============================================================
# SIDEBAR & MENU
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. EKASARI PERKASA")
    st.markdown("<div style='color: #f59e0b; font-size: 12px; margin-top: -10px;'>SMART INVENTORY SYSTEM</div>", unsafe_allow_html=True)
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Key: **{len(API_KEYS)}**")
    st.caption("Build v11.0 - Premium Design")
    
    st.markdown("---")
    st.markdown("### 📊 System Status")
    if sheet is not None:
        st.success("✅ Sheets: Connected")
    else:
        st.error("❌ Sheets: Disconnected")
    if FIREBASE_AVAILABLE and firebase_bucket:
        st.success("✅ Firebase: Connected")
    else:
        st.error("❌ Firebase: Disconnected")
    
    # SIGNATURE DI SIDEBAR
    st.markdown("---")
    st.markdown("""
    <div class="signature-box" style="margin-top: 40px; padding: 25px;">
        <div class="signature-text" style="font-size: 26px;">Sebastian Sasmita.JR</div>
        <div class="signature-year">© 2026 - PT. Ekasari Perkasa</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# MAIN APP LOGIC
# ============================================================
if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 5])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=110)
    with col_text:
        st.markdown("<h1>PT. EKASARI PERKASA</h1>", unsafe_allow_html=True)
        st.markdown("<p>Sistem Inventory Data Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if sheet is not None:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                with s1: st.metric("📄 Total Dokumen", f"{len(df)} Unit")
                with s2: st.metric("🏢 Klien Terakhir", str(df.iloc[-1, 0]) if len(df) > 0 else "-")
                with s3: st.metric("🕐 Update", str(df.iloc[-1, 1]).split(" ")[0] if len(df) > 0 else "-")
                st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.info("📭 Database kosong")
        except Exception as e: 
            st.error(f"Error load  {e}")
    else:
        st.warning("⚠️ Sheets tidak terkoneksi. Cek sidebar.")

elif menu == "📤 Scan & Upload":
    st.markdown('<div class="title-logo">', unsafe_allow_html=True)
    col_logo2, col_title = st.columns([1, 8])
    with col_logo2:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=60)
    with col_title:
        st.markdown("<h2 style='margin:0; color: #1e3a5f;'>Ekasari Perkasa Inventory Dashboard</h2>", unsafe_allow_html=True)
        st.markdown("<p style='margin:5px 0 0 0; color: #64748b;'>Upload & Analisis Dokumen Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("🏢 Nama Perusahaan")
        divisi = st.selectbox("📋 Divisi", ["EXPORT", "IMPORT", "DOMESTIK"])
    with c_b:
        kategori = st.selectbox("📁 Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "Lainnya"])
        id_doc = st.text_input("🔢 ID Document (No AWB/Invoice)")

    st.markdown("---")
    upload_method = st.radio("📥 Metode Input", ["📁 Upload File", "📷 Gunakan Kamera"], horizontal=True)
    u_file = None
    if upload_method == "📁 Upload File":
        u_file = st.file_uploader("Upload Dokumen (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key="file_uploader")
    else:
        st.info("📸 Kamera hanya aktif setelah tombol ditekan")
        u_file = st.camera_input("📷 Ambil Foto Dokumen", key="camera_input")

    if u_file and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi Nama Perusahaan Ya Sayank Muachh :-D")
        elif sheet is None:
            st.error("❌ Google Sheets tidak terkoneksi! Cek sidebar.")
        else:
            with st.spinner("🔍 Memvalidasi dokumen..."):
                validation = validate_document_fields(u_file, nama_klien, divisi, kategori, id_doc)
            
            if validation["mismatches"]:
                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                st.markdown("### 🚨 PERINGATAN: Ketidaksesuaian Data")
                mismatch_df = pd.DataFrame(validation["mismatches"])
                st.table(mismatch_df[["field", "user_input", "detected"]])
                st.markdown("</div>", unsafe_allow_html=True)
                if not validation["can_proceed"]:
                    st.error(" UPLOAD DIBLOKIR!")
                    st.stop()
                else:
                    if not st.checkbox("✅ Ya, saya yakin dan ingin melanjutkan"):
                        st.stop()
            
            with st.spinner("System Sedang Menganalisis Data..."):
                hasil = proses_analisis_ai(u_file)
                if "❌" not in hasil and sheet is not None:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    doc_name = id_doc if id_doc else u_file.name
                    
                    # AUTO UPLOAD KE FIREBASE
                    cloud_link = None
                    with st.spinner("☁️ Mengupload ke Firebase Storage..."):
                        cloud_link, cloud_error = upload_to_firebase(u_file, nama_klien, kategori, doc_name)
                        if cloud_error:
                            st.warning(cloud_error)
                        elif cloud_link:
                            st.success(f"🔗 File tersimpan: [Lihat File]({cloud_link})")
                    
                    sheet.append_row([nama_klien, ts, doc_name, kategori, divisi, f"{hasil}\n\n☁️ Cloud: {cloud_link}" if cloud_link else hasil])
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("✅ Berhasil disimpan ke database!")
                    st.markdown('</div>', unsafe_allow_html=True)
                    with st.expander("📋 Hasil Analisis "):
                        st.info(hasil)
                else:
                    st.error(hasil)
    
    # SIGNATURE
    st.markdown("""
    <div class="signature-box">
        <div class="signature-text">Sebastian Sasmita.JR</div>
        <div class="signature-year">Created with ❤️ for PT. Ekasari Perkasa | © 2026</div>
    </div>
    """, unsafe_allow_html=True)

elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet is not None:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                st.dataframe(data, use_container_width=True)
            else:
                st.info("📭 Database kosong")
        except Exception as e: 
            st.error(f"Error: {e}")
    else:
        st.error("❌ Sheets tidak terkoneksi")
    
    # SIGNATURE
    st.markdown("""
    <div class="signature-box">
        <div class="signature-text">Sebastian Sasmita.JR</div>
        <div class="signature-year">System Developer | © 2026</div>
    </div>
    """, unsafe_allow_html=True)
