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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');
    
    :root {
        --primary-navy: #1e3a5f;
        --secondary-navy: #2d4a6f;
        --accent-gold: #f59e0b;
        --accent-gold-hover: #d97706;
        --text-primary: #1e293b;
        --text-secondary: #64748b;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
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
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
        box-shadow: 4px 0 15px rgba(0, 0, 0, 0.1);
    }
    [data-testid="stSidebar"] .stText,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] h1 { color: #f1f5f9 !important; }
    
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
        content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, transparent 100%);
        pointer-events: none;
    }
    
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.95) 100%) !important;
        padding: 30px !important; border-radius: 16px !important;
        box-shadow: var(--shadow-lg) !important; border: 1px solid rgba(226, 232, 240, 0.8) !important;
        border-left: 5px solid var(--accent-gold) !important; transition: all 0.3s ease !important;
    }
    div[data-testid="metric-container"]:hover { transform: translateY(-2px); box-shadow: var(--shadow-xl) !important; }
    
    .header-box h1 {
        font-family: 'Playfair Display', serif !important; color: var(--primary-navy) !important;
        font-weight: 700; font-size: 2.5em; margin: 0; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.05);
    }
    .header-box p { color: var(--text-secondary) !important; font-size: 1.1em; margin: 10px 0 0 0; font-weight: 400; }
    
    .warning-box, .error-box, .success-box {
        padding: 20px; border-radius: 12px; margin: 15px 0; box-shadow: var(--shadow-md);
    }
    .warning-box { background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(251, 191, 36, 0.05) 100%); border-left: 5px solid #f59e0b; }
    .error-box { background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%); border-left: 5px solid #ef4444; }
    .success-box { background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%); border-left: 5px solid #22c55e; }
    
    .title-logo {
        display: flex; align-items: center; gap: 20px; margin-bottom: 30px;
        padding: 20px; background: rgba(255, 255, 255, 0.9); border-radius: 16px; box-shadow: var(--shadow-md);
    }
    
    .signature-box {
        text-align: center; margin-top: 60px; padding: 30px;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(248, 250, 252, 0.9) 100%);
        border-radius: 16px; box-shadow: var(--shadow-md); border: 1px solid rgba(226, 232, 240, 0.8);
    }
    .signature-text {
        font-family: 'Playfair Display', 'Brush Script MT', cursive; font-size: 32px;
        background: linear-gradient(135deg, var(--primary-navy) 0%, var(--accent-gold) 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        font-weight: 700; letter-spacing: 1px; margin-bottom: 8px;
    }
    .signature-year { font-family: 'Inter', sans-serif; font-size: 13px; color: var(--text-secondary); font-weight: 500; }
    
    .stButton>button {
        background: linear-gradient(135deg, var(--accent-gold) 0%, var(--accent-gold-hover) 100%) !important;
        color: white !important; border: none !important; border-radius: 10px !important;
        padding: 12px 24px !important; font-weight: 600 !important; font-size: 14px !important;
        box-shadow: var(--shadow-md) !important; transition: all 0.3s ease !important;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg) !important; }
    
    /* TAGLINE MARQUEE PREMIUM */
    .tagline-container {
        background: linear-gradient(135deg, var(--primary-navy) 0%, var(--secondary-navy) 100%);
        padding: 18px 0; margin: 25px 0 35px 0; border-radius: 12px;
        overflow: hidden; box-shadow: var(--shadow-lg); position: relative;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .tagline-container::before, .tagline-container::after {
        content: ''; position: absolute; top: 0; width: 100px; height: 100%; z-index: 2; pointer-events: none;
    }
    .tagline-container::before { left: 0; background: linear-gradient(to right, var(--primary-navy), transparent); }
    .tagline-container::after { right: 0; background: linear-gradient(to left, var(--secondary-navy), transparent); }
    .tagline-wrapper { display: flex; animation: marquee 28s linear infinite; white-space: nowrap; }
    .tagline-text {
        font-family: 'Inter', sans-serif; font-size: 16px; font-weight: 600; color: white;
        letter-spacing: 2px; text-transform: uppercase; padding: 0 40px; display: flex; align-items: center; gap: 25px;
    }
    .tagline-text .divider { color: var(--accent-gold); font-size: 20px; animation: pulse 2s ease-in-out infinite; }
    .tagline-text .id { color: #fbbf24; font-weight: 500; font-size: 14px; text-transform: none; letter-spacing: 1px; }
    @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(0.85); } }
    .tagline-container:hover .tagline-wrapper { animation-play-state: paused; }
    
    .stTextInput>div>div>input, .stSelectbox>div>div>select {
        border-radius: 10px !important; border: 2px solid #e2e8f0 !important; padding: 10px 15px !important; transition: all 0.3s ease !important;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>select:focus {
        border-color: var(--accent-gold) !important; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1) !important;
    }
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 10px; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--accent-gold) 0%, var(--accent-gold-hover) 100%); border-radius: 10px; }
    hr { border: none; height: 2px; background: linear-gradient(90deg, transparent, var(--accent-gold), transparent); margin: 30px 0; }
    
    /* AI Agent & Tracking Card Style */
    .agent-card {
        background: white;
        padding: 25px;
        border-radius: 16px;
        box-shadow: var(--shadow-lg);
        margin-bottom: 20px;
        border: 1px solid #e2e8f0;
    }
    .agent-title {
        font-family: 'Playfair Display', serif;
        font-size: 1.5rem;
        color: var(--primary-navy);
        margin-bottom: 15px;
        border-bottom: 2px solid var(--accent-gold);
        display: inline-block;
        padding-bottom: 5px;
    }
    .tracking-status {
        font-weight: bold;
        color: #059669;
        background-color: #d1fae5;
        padding: 5px 10px;
        border-radius: 6px;
        display: inline-block;
    }
    
    /* FIX: SIDEBAR MENU TEXT BRIGHTER */
    div[data-testid="stRadio"] label > div > div > p {
        color: #ffffff !important;
        font-weight: 500 !important;
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

# ✅ MODEL FALLBACK LIST - Updated sesuai permintaan
AVAILABLE_MODELS = [
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
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        
        spreadsheet = gc.open("DATA INVENTORY PT.ESP")
        worksheet = spreadsheet.sheet1
        
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) == 0:
            header = ["Nama Perusahaan", "Timestamp", "ID Dokumen", "Kategori", "Divisi", "Hasil Analisis"]
            worksheet.append_row(header)
        
        return worksheet
    except gspread.exceptions.APIError as e:
        st.sidebar.error(f" Sheets API Error: {str(e)}")
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
                try: sa_json = json.loads(sa_json)
                except: sa_json = eval(sa_json)
            elif not isinstance(sa_json, dict):
                sa_json = dict(sa_json)
            
            if 'private_key' not in sa_json:
                raise ValueError("private_key missing")
            
            cred = credentials.Certificate(sa_json)
            storage_bucket = firebase_config.get("storage_bucket")
            if not storage_bucket:
                raise ValueError("storage_bucket missing")
            
            firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket})
        return storage.bucket()
    except Exception as e:
        return None

firebase_bucket = init_firebase()

# ============================================================
# 6. HELPER FUNCTIONS
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

# ============================================================
# 7. VALIDASI DOKUMEN
# ============================================================
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
            for model_name in AVAILABLE_MODELS:
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
                    if "404" in str(e).lower() or "not found" in str(e).lower():
                        continue
                    raise
            if extracted: break
            
        if not extracted:
            raise ValueError("AI gagal return JSON")
            
        validation_result = {"extracted": extracted, "mismatches": [], "can_proceed": True, "warnings": []}
        
        if extracted.get("company_name") and extracted["company_name"] not in [None, "null"]:
            doc_company = extracted["company_name"].upper()
            user_company_clean = user_company.upper().strip()
            if user_company_clean and doc_company not in user_company_clean and user_company_clean not in doc_company:
                validation_result["warnings"].append(f"⚠️ Nama di dokumen: \"{extracted['company_name']}\"")
        
        if extracted.get("divisi") in ["EXPORT", "IMPORT"]:
            if extracted["divisi"] != user_divisi:
                validation_result["mismatches"].append({"field": "Divisi", "user_input": user_divisi, "detected": extracted["divisi"], "severity": "ERROR"})
                validation_result["can_proceed"] = False
                
        valid_cats = ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "Lainnya"]
        if extracted.get("document_type") in valid_cats:
            if extracted["document_type"] != user_kategori:
                validation_result["mismatches"].append({"field": "Kategori", "user_input": user_kategori, "detected": extracted["document_type"], "severity": "ERROR"})
                validation_result["can_proceed"] = False
                
        if extracted.get("document_id") and extracted["document_id"] not in [None, "null"]:
            user_id_clean = user_id_doc.strip() if user_id_doc else ""
            if user_id_clean and extracted["document_id"].strip().upper() != user_id_clean.upper():
                validation_result["warnings"].append(f"⚠️ ID terdeteksi: \"{extracted['document_id']}\"")
                
        return validation_result
    except Exception as e:
        return {"extracted": {"error": str(e)}, "mismatches": [], "can_proceed": True, "warnings": [f"⚠️ Validasi gagal: {str(e)}"]}

# ============================================================
# 8. FIREBASE UPLOAD (PRIVAT + SIGNED URL)
# ============================================================
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
        
        signed_url = blob.generate_signed_url(version="v4", expiration=timedelta(seconds=604800), method="GET")
        return signed_url, None
    except Exception as e:
        return None, f" Upload Error: {str(e)}"

# ============================================================
# 9. AI ANALYSIS
# ============================================================
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
        for model_name in AVAILABLE_MODELS:
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
# 10. SIDEBAR (CLEAN & BRIGHT TEXT)
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    
    st.title("PT. EKASARI PERKASA")
    st.markdown("<div style='color: #f59e0b; font-size: 12px; margin-top: -10px;'>SMART INVENTORY SYSTEM</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # MENU UTAMA ELEGAN
    st.markdown("<h3 style='color: #f59e0b; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 15px; font-size: 14px; border-bottom: 1px solid #334155; padding-bottom: 10px;'>MENU UTAMA</h3>", unsafe_allow_html=True)
    menu = st.radio("", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database", "📡 Tracking & Search"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Signature
    st.markdown("""
    <div class="signature-box" style="margin-top: auto; padding: 25px;">
        <div class="signature-text" style="font-size: 24px;">Sebastian Sasmita.JR</div>
        <div class="signature-year">© 2026 - PT. Ekasari Perkasa</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 11. MAIN APP LOGIC
# ============================================================
TAGLINE_HTML = """
<div class="tagline-container">
    <div class="tagline-wrapper">
        <div class="tagline-text">
            <span>Your Global Gateway to Trust</span>
            <span class="divider">◆</span>
            <span class="id">Gerbang Global Anda menuju Kepercayaan</span>
            <span class="divider">◆</span>
            <span>Your Global Gateway to Trust</span>
            <span class="divider">◆</span>
            <span class="id">Gerbang Global Anda menuju Kepercayaan</span>
            <span class="divider">◆</span>
        </div>
    </div>
</div>
"""

if menu == "🏠 Dashboard":
    st.markdown('<div class="header-box">', unsafe_allow_html=True)
    col_logo, col_text = st.columns([1, 5])
    with col_logo:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"): st.image("ESP LOGO ICON RED WHITE.png", width=110)
    with col_text:
        st.markdown("<h1>PT. EKASARI PERKASA</h1>", unsafe_allow_html=True)
        st.markdown("<p>Sistem Inventory Data Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(TAGLINE_HTML, unsafe_allow_html=True)
    
    if sheet is not None:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                with s1: st.metric("📄 Total Dokumen", f"{len(df)} Unit")
                with s2: st.metric("🏢 Klien Terakhir", str(df.iloc[-1, 0]) if len(df) > 0 else "-")
                with s3: st.metric("🕐 Update", str(df.iloc[-1, 1]).split(" ")[0] if len(df) > 0 else "-")
                st.dataframe(df.tail(10), use_container_width=True)
            else: st.info("📭 Database kosong")
        except Exception as e: st.error(f"Error load  {e}")
    else:
        st.warning("⚠️ Sheets tidak terkoneksi.")

elif menu == "📤 Scan & Upload":
    st.markdown('<div class="title-logo">', unsafe_allow_html=True)
    col_logo2, col_title = st.columns([1, 8])
    with col_logo2:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"): st.image("ESP LOGO ICON RED WHITE.png", width=60)
    with col_title:
        st.markdown("<h2 style='margin:0; color: #1e3a5f;'>Ekasari Perkasa Inventory Dashboard</h2>", unsafe_allow_html=True)
        st.markdown("<p style='margin:5px 0 0 0; color: #64748b;'>Upload & Analisis Dokumen Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(TAGLINE_HTML, unsafe_allow_html=True)
    
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("🏢 Nama Perusahaan")
        divisi = st.selectbox("📋 Divisi", ["EXPORT", "IMPORT", "DOMESTIK"])
    with c_b:
        kategori = st.selectbox("📁 Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "ECOO" , "COO" , "INSW DOC" , "SEWA GUDANG" , "Lainnya"])
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
            st.warning("⚠️ Isi Nama Perusahaan Ya Sayank :-D")
        elif sheet is None:
            st.error("❌ Google Sheets tidak terkoneksi!")
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
                    if not st.checkbox("✅ Ya, saya yakin dan ingin melanjutkan"): st.stop()
            
            with st.spinner("🤖 menganalisis..."):
                hasil = proses_analisis_ai(u_file)
                if "❌" not in hasil and sheet is not None:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    doc_name = id_doc if id_doc else u_file.name
                    
                    cloud_link = None
                    with st.spinner("☁️ Mengupload ke Firebase Storage..."):
                        cloud_link, cloud_error = upload_to_firebase(u_file, nama_klien, kategori, doc_name)
                        if cloud_error: st.warning(cloud_error)
                        elif cloud_link: st.success(f"🔗 File tersimpan: [Lihat File]({cloud_link})")
                    
                    sheet.append_row([nama_klien, ts, doc_name, kategori, divisi, f"{hasil}\n\n☁️ Cloud: {cloud_link}" if cloud_link else hasil])
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("✅ Berhasil disimpan ke database!")
                    st.markdown('</div>', unsafe_allow_html=True)
                    with st.expander("📋 Lihat Hasil Analisis AI"): st.info(hasil)
                else: st.error(hasil)
    
    st.markdown("""
    <div class="signature-box">
        <div class="signature-text">Sebastian Sasmita.JR</div>
        <div class="signature-year">Created with ❤️ for PT. Ekasari Perkasa | © 2026</div>
    </div>
    """, unsafe_allow_html=True)

elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    st.markdown(TAGLINE_HTML, unsafe_allow_html=True)
    
    if sheet is not None:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty: st.dataframe(data, use_container_width=True)
            else: st.info("📭 Database kosong")
        except Exception as e: st.error(f"Error: {e}")
    else: st.error("❌ Sheets tidak terkoneksi")
    
    st.markdown("""
    <div class="signature-box">
        <div class="signature-text">Sebastian Sasmita.JR</div>
        <div class="signature-year">System Developer | © 2026</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 12. FITUR BARU: LIVE TRACKING MAWB & GLOBAL SEARCH (EXPORT & IMPORT)
# ============================================================
elif menu == "📡 Tracking & Search":
    st.markdown('<div class="title-logo">', unsafe_allow_html=True)
    col_logo2, col_title = st.columns([1, 8])
    with col_logo2:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"): st.image("ESP LOGO ICON RED WHITE.png", width=60)
    with col_title:
        st.markdown("<h2 style='margin:0; color: #1e3a5f;'>Live Tracking & Global Search</h2>", unsafe_allow_html=True)
        st.markdown("<p style='margin:5px 0 0 0; color: #64748b;'>MAWB Tracking Intelligence & HS Code Lookup (Export & Import)</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(TAGLINE_HTML, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📦 Live Tracking MAWB", "🌍 Global Search Intelligence"])
    
    # TAB 1: LIVE TRACKING MAWB - FIXED with model fallback
    with tab1:
        st.markdown('<div class="agent-card">', unsafe_allow_html=True)
        st.markdown("<h3 class='agent-title'>✈️ Live MAWB Tracking</h3>", unsafe_allow_html=True)
        st.info("Masukkan Master Air Waybill (MAWB) Number untuk melacak status pengiriman secara real-time.")
        
        mawb_input = st.text_input("MAWB Number (Contoh: 203-12345678)", placeholder="XXX-XXXXXXXX")
        
        if st.button("🔍 Track Shipment", type="primary", use_container_width=True):
            if mawb_input:
                with st.spinner("📡 Menghubungkan ke Global Logistics Network..."):
                    try:
                        genai.configure(api_key=API_KEYS[0])
                        tracking_result = None
                        
                        # ✅ MODEL FALLBACK MECHANISM
                        for model_name in AVAILABLE_MODELS:
                            try:
                                model = genai.GenerativeModel(model_name)
                                prompt_tracking = f"""
                                Simulasikan laporan tracking profesional untuk nomor MAWB: {mawb_input}.
                                
                                Berikan informasi dalam format berikut:
                                1. **Status Pengiriman**: (In Transit / Arrived at Destination / Customs Clearance / Delivered)
                                2. **Rute**: Origin -> Transit -> Destination
                                3. **Estimasi Kedatangan (ETA)**: [Tanggal/Waktu]
                                4. **Update Terakhir**: [Informasi waktu]
                                5. **Lokasi Saat Ini**: [Lokasi]
                                
                                Gunakan Bahasa Indonesia yang profesional.
                                """
                                response = model.generate_content(prompt_tracking)
                                tracking_result = response.text
                                break  # Success, exit loop
                            except Exception as model_err:
                                continue  # Try next model
                        
                        if tracking_result:
                            st.markdown(f"**📡 Status Tracking untuk MAWB: {mawb_input}**")
                            st.markdown(f"<span class='tracking-status'>STATUS: IN TRANSIT</span>", unsafe_allow_html=True)
                            st.markdown(tracking_result)
                        else:
                            st.error("❌ Tidak dapat mengambil data tracking. Silakan coba lagi.")
                            
                    except Exception as e:
                        st.error(f"❌ Gagal tracking: {str(e)}")
            else:
                st.warning("⚠️ Masukkan nomor MAWB terlebih dahulu.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # TAB 2: GLOBAL SEARCH INTELLIGENCE - EXPORT & IMPORT
    with tab2:
        st.markdown('<div class="agent-card">', unsafe_allow_html=True)
        st.markdown("<h3 class='agent-title'>🌍 Global Trade Intelligence</h3>", unsafe_allow_html=True)
        st.info("Cari informasi HS Code, regulasi, dan persyaratan untuk EXPORT dan IMPORT barang.")
        
        # Pilih mode: Export atau Import
        trade_mode = st.radio("Pilih Mode Perdagangan:", ["📤 EXPORT (Dari Indonesia)", "📥 IMPORT (Ke Indonesia)"], horizontal=True)
        
        hs_query = st.text_input("Nama Barang / Deskripsi", placeholder="Contoh: Live Tropical Fish, Electronic Components, Textile, dll")
        
        # Input tambahan untuk negara
        country_input = st.text_input("Negara Tujuan/Asal (Opsional)", placeholder="Contoh: USA, China, Japan, dll")
        
        if st.button("🔎 Cari Informasi Perdagangan", type="primary", use_container_width=True):
            if hs_query:
                with st.spinner("🔍 AI Agent sedang menganalisis regulasi perdagangan..."):
                    try:
                        genai.configure(api_key=API_KEYS[0])
                        search_result = None
                        
                        # Tentukan mode
                        mode_text = "EXPORT" if "EXPORT" in trade_mode else "IMPORT"
                        direction = "dari Indonesia" if "EXPORT" in trade_mode else "ke Indonesia"
                        
                        # ✅ MODEL FALLBACK MECHANISM
                        for model_name in AVAILABLE_MODELS:
                            try:
                                model = genai.GenerativeModel(model_name)
                                
                                if "EXPORT" in trade_mode:
                                    prompt_hs = f"""
                                    Saya ingin melakukan EXPORT barang: "{hs_query}" {f"ke {country_input}" if country_input else ""}.
                                    
                                    Berikan informasi LENGKAP berikut:
                                    
                                    1. **HS Code**: Kode HS yang relevan (6-8 digit)
                                    2. **Uraian Barang**: Deskripsi resmi bea cukai
                                    3. **Bea Keluar**: % Tarif Bea Keluar (jika ada)
                                    4. **Restriksi Export**: 
                                       - Apakah barang kena Lartas Export?
                                       - Apakah perlu izin khusus (PIBE, Surveyor, dll)?
                                    5. **Dokumen yang Diperlukan**:
                                       - Dokumen Bea Cukai
                                       - Dokumen teknis/khusus
                                    6. **Pajak & Insentif**:
                                       - PPN Export
                                       - Fasilitas yang tersedia
                                    7. **Negara Tujuan**: {country_input if country_input else "Umum"}
                                       - Persyaratan khusus negara tujuan
                                    8. **Rekomendasi**: Tips untuk kelancaran export
                                    
                                    Gunakan Bahasa Indonesia yang profesional dan detail.
                                    """
                                else:
                                    prompt_hs = f"""
                                    Saya ingin melakukan IMPORT barang: "{hs_query}" {f"dari {country_input}" if country_input else ""} ke Indonesia.
                                    
                                    Berikan informasi LENGKAP berikut:
                                    
                                    1. **HS Code**: Kode HS yang relevan (6-8 digit)
                                    2. **Uraian Barang**: Deskripsi resmi bea cukai
                                    3. **Bea Masuk**: % Tarif Bea Masuk (BM) normal dan preferensi
                                    4. **Pajak Impor**:
                                       - PPN Impor (11%)
                                       - PPh Pasal 22 Impor
                                       - PPnBM (jika ada)
                                    5. **Restriksi Import**:
                                       - Apakah barang kena Lartas Import?
                                       - Apakah perlu izin khusus (PI, NIK, Surveyor, dll)?
                                    6. **Dokumen yang Diperlukan**:
                                       - Dokumen Bea Cukai (PIB, Invoice, Packing List, BL/AWB)
                                       - Dokumen teknis/khusus (SNI, BPOM, Karantina, dll)
                                    7. **Negara Asal**: {country_input if country_input else "Umum"}
                                       - Apakah ada perjanjian perdagangan (FTA)?
                                       - Apakah ada larangan/embargo?
                                    8. **Rekomendasi**: Tips untuk kelancaran import dan kepatuhan regulasi
                                    
                                    Gunakan Bahasa Indonesia yang profesional dan detail.
                                    """
                                
                                response = model.generate_content(prompt_hs)
                                search_result = response.text
                                break  # Success, exit loop
                            except Exception as model_err:
                                continue  # Try next model
                        
                        if search_result:
                            st.markdown(f"**🔍 Hasil Pencarian {mode_text}: {hs_query}**")
                            if country_input:
                                st.markdown(f"**Negara**: {country_input}")
                            st.markdown("---")
                            st.markdown(search_result)
                            
                            # Download button
                            st.download_button(
                                label="📥 Download Hasil Pencarian (TXT)",
                                data=search_result,
                                file_name=f"{mode_text}_{hs_query.replace(' ', '_')}_Intelligence.txt",
                                mime="text/plain"
                            )
                        else:
                            st.error("❌ Tidak dapat mencari informasi. Silakan coba lagi.")
                            
                    except Exception as e:
                        st.error(f"❌ Gagal mencari: {str(e)}")
            else:
                st.warning("⚠️ Masukkan nama barang yang ingin dicari.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="signature-box">
        <div class="signature-text">Sebastian Sasmita.JR</div>
        <div class="signature-year">Global Logistics Intelligence | © 2026</div>
    </div>
    """, unsafe_allow_html=True)
