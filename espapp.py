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
    .warning-box { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 5px; margin: 10px 0; }
    .error-box { background-color: #f8d7da; border-left: 5px solid #dc3545; padding: 15px; border-radius: 5px; margin: 10px 0; }
    .success-box { background-color: #d4edda; border-left: 5px solid #28a745; padding: 15px; border-radius: 5px; margin: 10px 0; }
    .title-logo { display: flex; align-items: center; gap: 15px; }
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
# 4. KONEKSI GOOGLE SHEETS (FIXED)
# ============================================================
@st.cache_resource
def init_gsheet():
    try:
        creds_info = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        gc = gspread.authorize(creds)
        
        spreadsheet = gc.open("DATA INVENTORY PT.ESP")
        sheet = spreadsheet.sheet1
        
        # Test akses
        sheet.get_all_records()
        
        return sheet
    except Exception as e:
        st.sidebar.error(f" Sheets Error: {str(e)}")
        return None

sheet = init_gsheet()

# ============================================================
# 5. FIREBASE STORAGE INITIALIZATION (FIXED PARSING)
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
            
            # FIX: Handle parsing dari Streamlit Secrets
            if isinstance(sa_json, str):
                try:
                    sa_json = json.loads(sa_json)
                except:
                    sa_json = eval(sa_json)
            elif not isinstance(sa_json, dict):
                # Convert jika bukan dict
                sa_json = dict(sa_json)
            
            # Validasi
            if 'private_key' not in sa_json:
                raise ValueError("private_key missing in service_account")
            
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
# 6-11. HELPER FUNCTIONS, VALIDASI, UPLOAD, AI, MAIN LOGIC
# (Sama seperti source code sebelumnya - tidak berubah)
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
    instruksi = (
        "Kamu adalah AI Inventory PT ESP. "
        "Ekstrak informasi penting dari dokumen ini. "
        "Sajikan secara ringkas dan terstruktur."
    )
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
        validation_prompt = f"""
Analisis dokumen dan ekstrak dalam JSON:
{{
  "company_name": "Nama perusahaan",
  "divisi": "EXPORT atau IMPORT",
  "document_type": "MAWB/Invoice/Surat Jalan/DOKAP/Perizinan/PEB/PIB/SPPB/Lainnya",
  "document_id": "Nomor dokumen",
  "confidence": "HIGH atau LOW"
}}
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
                    if "404" in str(e).lower() or "not found" in str(e).lower():
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
        st.toast(" Dari cache", icon="✅")
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
                if "quota" in err or "exhausted" in err:
                    st.toast("⚠️ Limit, coba model lain...", icon="🔄")
                    continue
                return f"❌ Error API: {e}"
    return "❌ Gagal. Pastikan Billing aktif."

# ============================================================
# SIDEBAR & MENU
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. EKASARI PERKASA DATABASE")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Key: **{len(API_KEYS)}**")
    st.caption("Build v10.3 - Fixed Init")
    
    st.markdown("---")
    st.markdown("### Status")
    if sheet:
        st.success("✅ Sheets: Connected")
    else:
        st.error("❌ Sheets: Disconnected")
    if FIREBASE_AVAILABLE and firebase_bucket:
        st.success("✅ Firebase: Connected")
    else:
        st.error("❌ Firebase: Disconnected")

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
        st.markdown("<h1 style='margin:0; color:#0e2135;'>PT. EKASARI PERKASA</h1>", unsafe_allow_html=True)
        st.markdown("<p style='margin:0; color:#666;'>Sistem Inventory Data Otomatis</p>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if sheet:
        try:
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                s1, s2, s3 = st.columns(3)
                with s1: st.metric("Total Dokumen", f"{len(df)} Unit")
                with s2: st.metric("Klien Terakhir", str(df.iloc[-1, 0]))
                with s3: st.metric("Update", str(df.iloc[-1, 1]).split(" ")[0])
                st.dataframe(df.tail(10), use_container_width=True)
        except Exception as e: 
            st.error(f"Error load data: {e}")
    else:
        st.warning("⚠️ Sheets tidak terkoneksi. Cek sidebar untuk detail error.")

elif menu == "📤 Scan & Upload":
    st.markdown('<div class="title-logo">', unsafe_allow_html=True)
    col_logo2, col_title = st.columns([1, 8])
    with col_logo2:
        if os.path.exists("ESP LOGO ICON RED WHITE.png"):
            st.image("ESP LOGO ICON RED WHITE.png", width=60)
    with col_title:
        st.header("Ekasari Perkasa Inventory Dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("Nama Perusahaan")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT", "DOMESTIK"])
    with c_b:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "Lainnya"])
        id_doc = st.text_input("ID Document (No AWB/Invoice)")

    st.markdown("---")
    upload_method = st.radio(" Metode Input", ["📁 Upload File", "📷 Gunakan Kamera"], horizontal=True)
    u_file = None
    if upload_method == "📁 Upload File":
        u_file = st.file_uploader("Upload Dokumen (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key="file_uploader")
    else:
        st.info("📸 Kamera hanya aktif setelah tombol ditekan")
        u_file = st.camera_input("📷 Ambil Foto Dokumen", key="camera_input")

    upload_to_cloud_option = st.checkbox("☁️ Simpan file fisik ke Firebase", value=True)

    if u_file and st.button("🚀 PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi Nama Perusahaan ya sayank muach :-D")
        elif not sheet:
            st.error("❌ Google Sheets tidak terkoneksi! Cek sidebar untuk detail.")
        else:
            with st.spinner(" Memvalidasi..."):
                validation = validate_document_fields(u_file, nama_klien, divisi, kategori, id_doc)
            
            if validation["mismatches"]:
                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                st.markdown("### 🚨 PERINGATAN: Ketidaksesuaian Data")
                mismatch_df = pd.DataFrame(validation["mismatches"])
                mismatch_df["Status"] = mismatch_df["severity"].apply(lambda x: "❌ ERROR" if x == "ERROR" else "⚠️ WARNING")
                st.table(mismatch_df[["field", "user_input", "detected", "Status"]].rename(columns={
                    "field": "Field", "user_input": "Input Anda", "detected": "Terdeteksi AI", "Status": "Status"
                }))
                if validation["warnings"]:
                    st.markdown("**Catatan:**")
                    for w in validation["warnings"]: st.markdown(f"- {w}")
                st.markdown("</div>", unsafe_allow_html=True)
                if not validation["can_proceed"]:
                    st.error(" UPLOAD DIBLOKIR!")
                    st.stop()
                else:
                    st.warning("⚠️ Perbedaan minor. Lanjutkan?")
                    if not st.checkbox("✅ Ya, lanjutkan"):
                        st.stop()
            elif validation["warnings"]:
                st.markdown('<div class="warning-box">', unsafe_allow_html=True)
                for w in validation["warnings"]: st.markdown(f"- {w}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with st.spinner(" Menganalisis..."):
                hasil = proses_analisis_ai(u_file)
                if "❌" not in hasil:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    doc_name = id_doc if id_doc else u_file.name
                    cloud_link = None
                    if upload_to_cloud_option:
                        with st.spinner(" Uploading..."):
                            cloud_link, cloud_error = upload_to_firebase(u_file, nama_klien, kategori, doc_name)
                            if cloud_error:
                                st.warning(cloud_error)
                            elif cloud_link:
                                st.success(f"🔗 File tersimpan: [Link]({cloud_link})")
                    sheet.append_row([nama_klien, ts, doc_name, kategori, divisi, f"{hasil}\n\n☁️ Cloud: {cloud_link}" if cloud_link else hasil])
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("✅ Berhasil disimpan!")
                    st.markdown('</div>', unsafe_allow_html=True)
                    with st.expander("📋 Hasil Analisis"):
                        st.info(hasil)
                else:
                    st.error(hasil)

elif menu == "📑 Full Database":
    st.header("📊 Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                st.dataframe(data, use_container_width=True)
                csv = data.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 Download CSV", data=csv, file_name="inventory_esp.csv", mime="text/csv")
            else: st.info("📭 Database kosong")
        except Exception as e: st.error(f"Error: {e}")
    else:
        st.error("❌ Sheets tidak terkoneksi")
