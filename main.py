import streamlit as st
from agent1_duplicates import run_agent1
from agent2_heavy_files import run_agent2
from agent3_whatsapp_backup import run_agent3

st.set_page_config(page_title="📦 GDrive Space Fixer", layout="centered")
st.title("📦 Google Drive Space Fixer")
st.markdown("Solve 'Google Drive Full' with AI-powered agents")

# Agent 1
if st.button("🧹 Remove Duplicate Images from Drive"):
    with st.spinner("Running Agent 1..."):
        logs = run_agent1()
    st.success("✅ Done")
    st.code(logs)

# Agent 2
if st.button("📤 Move & Compress Heavy Files to USB"):
    with st.spinner("Running Agent 2..."):
        logs = run_agent2()
    st.success("✅ Done")
    st.code(logs)

# Agent 3
if st.button("📱 WhatsApp Backup Shrinker"):
    with st.spinner("Running Agent 3..."):
        logs = run_agent3()
    st.success("✅ Done")
    st.code(logs)
