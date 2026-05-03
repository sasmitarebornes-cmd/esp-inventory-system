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
import re
from datetime import datetime

# 🔹 Safe import untuk Drive API
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    DRIVE_LIB_AVAILABLE = True
except ImportError:
    DRIVE_LIB_AVAILABLE = False

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

# ✅ PERBAIKAN: Gunakan model yang stabil (Gemini 3 belum tersedia publik, ganti ke 1.5/2.0)
MODEL_LIST = [
    "gemini-1.5-flash",             # Model stabil utama
    "gemini-1.5-pro",               # Akurasi tinggi
    "gemini-2.0-flash-exp"          # Model terbaru jika tersedia
    "gemini-3-flash",               # Model utama tahun 2026
    "gemini-3-flash-preview",       # Versi preview terbaru
    "gemini-3.1-flash-lite-preview",# Versi hemat kuota
    "gemini-2.5-pro"                # Fallback seri 2.5
]



if not API_KEYS:
    st.error("❌ Tidak ada GOOGLE_API_KEY ditemukan di Streamlit Secrets!")
    st.stop()

# ============================================================
# 4. KONEKSI GOOGLE SHEETS & DRIVE (FIXED)
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
        # Return sheet AND credentials
        return gc.open("DATA INVENTORY PT.ESP").sheet1, creds
    except Exception as e:
        st.sidebar.error(f"Gagal koneksi Sheets: {e}")
        return None, None

sheet, drive_creds = init_gsheet()

# Simpan credentials ke session state global
if drive_creds:
    st.session_state.drive_creds = drive_creds

# ============================================================
# 5. HELPER FUNCTIONS
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
        "Ekstrak informasi penting dari dokumen ini: "
        "Semua detail dokumen, "
        "Sajikan secara ringkas dan terstruktur. "
        "Lakukan deep analyze."
    )
    if file_input.type == "application/pdf":
        file_input.seek(0)
        pdf_data = file_input.read()
        return [{"mime_type": "application/pdf", "data": pdf_data}, instruksi]
    else:
        buf = compress_image(file_input)
        return [Image.open(buf), instruksi]

# ============================================================
# 6. FUNGSI VALIDASI KOMPREHENSIF DOKUMEN
# ============================================================
def validate_document_fields(file_input, user_company, user_divisi, user_kategori, user_id_doc):
    """
    Analisis dokumen dan validasi SEMUA field input user.
    """
    try:
        file_input.seek(0)
        
        validation_prompt = f"""
Kamu adalah validator dokumen logistik PT. Ekasari Perkasa.
Analisis dokumen ini dan ekstrak informasi berikut dalam format JSON murni (tanpa markdown):

{{
  "company_name": "Nama perusahaan/klien yang tertera",
  "divisi": "EXPORT atau IMPORT (PEB=EXPORT, PIB=IMPORT)",
  "document_type": "Salah satu: MAWB, Invoice, Surat Jalan, DOKAP, Perizinan, PEB, PIB, SPPB, Lainnya",
  "document_id": "Nomor dokumen utama (No AWB, Invoice, dll)",
  "confidence": "HIGH atau LOW"
}}

Instruksi:
1. Output HANYA JSON.
2. Divisi: PEB/MAWB Export = EXPORT, PIB/MAWB Import = IMPORT.
3. Jika tidak ada info, gunakan null.
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
        # ✅ FIX: Gunakan fallback model seperti fungsi utama
        for api_key in API_KEYS:
            genai.configure(api_key=api_key)
            for model_name in MODEL_LIST:
                try:
                    mdl = genai.GenerativeModel(model_name)
                    response = mdl.generate_content(konten)
                    hasil = response.text.strip()
                    
                    # Bersihkan markdown jika ada
                    if "```json" in hasil:
                        hasil = hasil.split("```json")[1].split("```")[0].strip()
                    elif "```" in hasil:
                        hasil = hasil.split("```")[1].strip()
                    
                    extracted = json.loads(hasil)
                    break
                except Exception as e:
                    err = str(e).lower()
                    if "404" in err or "not found" in err:
                        continue # Coba model berikutnya
                    raise
            if extracted: break
            
        if not extracted:
            raise ValueError("AI gagal mengembalikan JSON valid")
            
        # --- LOGIKA VALIDASI ---
        validation_result = {
            "extracted": extracted,
            "mismatches": [],
            "can_proceed": True,
            "warnings": []
        }
        
        # 1. Validasi Nama Perusahaan (WARNING)
        if extracted.get("company_name") and extracted["company_name"] not in [None, "null"]:
            doc_company = extracted["company_name"].upper()
            user_company_clean = user_company.upper().strip()
            if user_company_clean and doc_company not in user_company_clean and user_company_clean not in doc_company:
                validation_result["warnings"].append(f"⚠️ Nama di dokumen terdeteksi: \"{extracted['company_name']}\"")
        
        # 2. Validasi Divisi (ERROR CRITICAL)
        if extracted.get("divisi") in ["EXPORT", "IMPORT"]:
            if extracted["divisi"] != user_divisi:
                validation_result["mismatches"].append({
                    "field": "Divisi", 
                    "user_input": user_divisi, 
                    "detected": extracted["divisi"], 
                    "severity": "ERROR"
                })
                validation_result["can_proceed"] = False
                
        # 3. Validasi Kategori (ERROR CRITICAL)
        valid_cats = ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan", "PEB", "PIB", "SPPB", "Lainnya"]
        if extracted.get("document_type") in valid_cats:
            if extracted["document_type"] != user_kategori:
                validation_result["mismatches"].append({
                    "field": "Kategori Dokumen", 
                    "user_input": user_kategori, 
                    "detected": extracted["document_type"], 
                    "severity": "ERROR"
                })
                validation_result["can_proceed"] = False
                
        # 4. Validasi ID Document (WARNING)
        if extracted.get("document_id") and extracted["document_id"] not in [None, "null"]:
            user_id_clean = user_id_doc.strip() if user_id_doc else ""
            if user_id_clean and extracted["document_id"].strip().upper() != user_id_clean.upper():
                validation_result["warnings"].append(f"⚠️ ID dokumen terdeteksi: \"{extracted['document_id']}\"")
                
        return validation_result
        
    except Exception as e:
        return {
            "extracted": {"error": str(e)},
            "mismatches": [],
            "can_proceed": True,
            "warnings": [f"⚠️ Validasi otomatis gagal: {str(e)}. Lanjutkan manual."]
        }

# ============================================================
# 7. GOOGLE DRIVE UPLOAD (FINAL FIX)
# ============================================================
def upload_to_drive(file_input, company_name, category, doc_id=None):
    if not DRIVE_LIB_AVAILABLE:
        return None, "⚠️ Library google-api-python-client belum terinstall."
    
    creds = st.session_state.get("drive_creds")
    if not creds:
        return None, "❌ Kredensial Drive tidak tersedia. Pastikan service account benar."
    
    try:
        # ✅ FIX: Ambil Folder ID dari secrets
        folder_id = st.secrets.get("DRIVE_FOLDER_ID")
        
        if not folder_id:
            return None, "❌ ERROR: DRIVE_FOLDER_ID kosong di Streamlit Secrets! Isi ID folder Anda."
        
        if folder_id == "root":
            return None, "❌ ERROR: DRIVE_FOLDER_ID tidak boleh 'root'. Service account tidak punya kuota root. Masukkan ID folder yang di-share ke Service Account."
        
        # Prepare file data
        file_input.seek(0)
        file_bytes = file_input.read()
        filename = file_input.name or f"DOC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        mime_type = file_input.type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        now = datetime.now()
        folder_structure = [
            company_name.strip(),
            str(now.year),
            now.strftime("%Y-%m-%d"),
            category
        ]
        
        drive_service = build("drive", "v3", credentials=creds)
        parent_id = folder_id  # Mulai dari folder yang di-share
        
        for folder_name in folder_structure:
            query = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{folder_name}' "
                f"and '{parent_id}' in parents "
                f"and trashed=false"
            )
            results = drive_service.files().list(
                q=query, spaces="drive", fields="files(id, name)", supportsAllDrives=True
            ).execute()
            folders = results.get("files", [])
            
            if folders:
                parent_id = folders[0]["id"]
            else:
                folder_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id]
                }
                folder = drive_service.files().create(
                    body=folder_metadata, fields="id", supportsAllDrives=True
                ).execute()
                parent_id = folder.get("id")
        
        file_metadata = {
            "name": f"{doc_id}_{filename}" if doc_id else filename,
            "parents": [parent_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True
        ).execute()
        
        return uploaded_file.get("webViewLink"), None
        
    except Exception as e:
        error_msg = str(e)
        if "storageQuotaExceeded" in error_msg or "do not have storage quota" in error_msg:
            return None, "❌ Service account tidak punya kuota. Pastikan Anda men-share folder pribadi Anda ke email Service Account!"
        return None, f" Drive Upload Error: {error_msg}"

# ============================================================
# 8. FUNGSI ANALISIS AI
# ============================================================
def proses_analisis_ai(file_input):
    if "ai_cache" not in st.session_state:
        st.session_state.ai_cache = {}
    fhash = get_file_hash(file_input)
    
    if fhash in st.session_state.ai_cache:
        st.toast("⚡ Hasil dari cache.", icon="✅")
        return st.session_state.ai_cache[fhash]

    try:
        konten = build_content(file_input)
    except Exception as e:
        return f"❌ Gagal membaca file: {e}"

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
                    st.toast("⚠️ Limit terdeteksi, mencoba model berikutnya...", icon="🔄")
                    continue
                return f"❌ Error API: {e}"

    return "❌ Gagal. Pastikan Billing aktif."

# ============================================================
# 9. SIDEBAR & MENU
# ============================================================
with st.sidebar:
    if os.path.exists("ESP LOGO ICON RED WHITE.png"):
        st.image("ESP LOGO ICON RED WHITE.png", width=160)
    st.title("PT. EKASARI PERKASA DATABASE")
    st.markdown("---")
    menu = st.radio("MENU UTAMA", ["🏠 Dashboard", "📤 Scan & Upload", "📑 Full Database"])
    st.markdown("---")
    st.caption(f"🔑 API Key aktif: **{len(API_KEYS)}**")
    st.caption("Build v9.1 - Full Auto-Validation & Stable Models")
    
    st.markdown("---")
    st.markdown("### 🔧 System Status")
    if drive_creds:
        st.success("✅ Drive credentials tersedia")
    else:
        st.error(" Drive credentials gagal")
    
    if "DRIVE_FOLDER_ID" in st.secrets:
        st.success(f"✅ Folder ID: `{st.secrets['DRIVE_FOLDER_ID'][:15]}...`")
    else:
        st.error("❌ Folder ID hilang di Secrets")

# ============================================================
# 10. MAIN APP LOGIC
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
        except: st.info("Dashboard siap!")

elif menu == "📤 Scan & Upload":
    st.header("📤 Ekasari Perkasa Inventory Dashboard")
    c_a, c_b = st.columns(2)
    with c_a:
        nama_klien = st.text_input("Nama Perusahaan")
        divisi = st.selectbox("Divisi", ["EXPORT", "IMPORT"])
    with c_b:
        kategori = st.selectbox("Kategori", ["MAWB", "Invoice", "Surat Jalan", "DOKAP", "Perizinan" , "PEB" , "PIB" , "SPPB" , "Lainnya"])
        id_doc = st.text_input("ID Document (No AWB/Invoice)")

    st.markdown("---")
    upload_method = st.radio("📥 Metode Input", ["📁 Upload File", " Gunakan Kamera"], horizontal=True)
    
    u_file = None
    
    if upload_method == "📁 Upload File":
        u_file = st.file_uploader("Upload Dokumen (PDF/JPG/PNG)", type=["pdf", "jpg", "jpeg", "png"], key="file_uploader")
    else:
        st.info("📸 Kamera hanya aktif setelah Anda menekan tombol di bawah")
        u_file = st.camera_input("📷 Ambil Foto Dokumen", key="camera_input")

    upload_to_drive_option = st.checkbox("️ Simpan file fisik ke Google Drive", value=True)

    if u_file and st.button(" PROSES & SIMPAN", use_container_width=True, type="primary"):
        if not nama_klien.strip():
            st.warning("⚠️ Isi dulu Nama Perusahaannya Ya Sayank muach ")
        else:
            # 1. VALIDASI OTOMATIS
            with st.spinner(" Memvalidasi kesesuaian data dokumen..."):
                validation = validate_document_fields(u_file, nama_klien, divisi, kategori, id_doc)
            
            # 2. CEK HASIL VALIDASI
            if validation["mismatches"]:
                st.markdown('<div class="error-box">', unsafe_allow_html=True)
                st.markdown("### 🚨 PERINGATAN: Ketidaksesuaian Data")
                
                mismatch_df = pd.DataFrame(validation["mismatches"])
                mismatch_df["Status"] = mismatch_df["severity"].apply(lambda x: "❌ ERROR" if x == "ERROR" else "️ WARNING")
                st.table(mismatch_df[["field", "user_input", "detected", "Status"]].rename(columns={
                    "field": "Field", "user_input": "Input Anda", "detected": "Terdeteksi AI", "Status": "Status"
                }))
                
                if validation["warnings"]:
                    st.markdown("**Catatan Tambahan:**")
                    for w in validation["warnings"]: st.markdown(f"- {w}")
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                if not validation["can_proceed"]:
                    st.error(" UPLOAD DIBLOKIR: Perbaiki Divisi atau Kategori Dokumen yang salah!")
                    st.stop()
                else:
                    st.warning("️ Terdapat perbedaan minor. Pastikan data sudah benar sebelum lanjut.")
                    if not st.checkbox("✅ Saya yakin data sudah benar, lanjutkan upload"):
                        st.stop()

            elif validation["warnings"]:
                st.markdown('<div class="warning-box">', unsafe_allow_html=True)
                for w in validation["warnings"]: st.markdown(f"- {w}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # 3. PROSES AI & SIMPAN
            with st.spinner("System Sedang Menganalisis Data..."):
                hasil = proses_analisis_ai(u_file)
                
                if "❌" not in hasil and sheet:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    doc_name = id_doc if id_doc else u_file.name
                    
                    drive_link = None
                    if upload_to_drive_option:
                        with st.spinner("📤 Mengupload ke Google Drive..."):
                            drive_link, drive_error = upload_to_drive(u_file, nama_klien, kategori, doc_name)
                            if drive_error:
                                st.warning(drive_error)
                            elif drive_link:
                                st.success(f"🔗 File tersimpan di Drive: [Link]({drive_link})")
                    
                    sheet.append_row([nama_klien, ts, doc_name, kategori, divisi, f"{hasil}\n\n📎 Drive: {drive_link}" if drive_link else hasil])
                    
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("✅ Berhasil disimpan ke Database!")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    with st.expander("📋 Hasil Analisis AI"):
                        st.info(hasil)
                        if validation["extracted"] and "error" not in validation["extracted"]:
                            st.json(validation["extracted"])
                else:
                    st.error(hasil)

elif menu == "📑 Full Database":
    st.header(" Full Inventory Log")
    if sheet:
        try:
            data = pd.DataFrame(sheet.get_all_records())
            if not data.empty:
                st.dataframe(data, use_container_width=True)
                csv = data.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 Download CSV", data=csv, file_name="inventory_esp.csv", mime="text/csv")
            else: st.info("📭 Database kosong")
        except Exception as e: st.error(f"Error: {e}")
