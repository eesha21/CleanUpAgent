import streamlit as st
import os
from agent1_duplicates import run_agent1
from agent2_heavy_files import run_agent2
from agent3_whatsapp_backup import run_agent3

st.set_page_config(page_title="📦 GDrive Space Fixer", layout="centered")
st.title("📦 Google Drive Space Fixer")
st.markdown("Solve 'Google Drive Full' with AI-powered agents")

# 1️⃣ Agent 1: Remove Duplicates
if st.button("🧹 Remove Duplicate Images from Drive"):
    with st.spinner("Running Agent 1..."):
        logs = run_agent1()
    st.success("✅ Agent 1 Done")
    st.code(logs)

# 2️⃣ Agent 2: Move & Compress Heavy Files (with File Picker as Folder Selector)
st.subheader("📤 Move & Compress Heavy Files to USB")

folder_file = st.file_uploader("📂 Upload any file from the target USB/external drive folder", type=None)

if folder_file:
    folder_path = os.path.dirname(folder_file.name)
    st.info(f"📁 Detected folder: {folder_path}")
else:
    folder_path = None

if st.button("📤 Run Agent 2"):
    if folder_path and os.path.isdir(folder_path):
        with st.spinner(f"Running Agent 2 on: {folder_path}"):
            logs = run_agent2(folder_path)
        st.success("✅ Agent 2 Completed")
        st.code(logs)
    else:
        st.error("❌ Please upload a file from the target folder to select it.")

# 3️⃣ Agent 3: WhatsApp Backup Shrinker
if st.button("📱 WhatsApp Backup Shrinker"):
    with st.spinner("Running Agent 3..."):
        logs = run_agent3()
    st.success("✅ Agent 3 Done")
    st.code(logs)
