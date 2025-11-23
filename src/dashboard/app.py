import streamlit as st
import requests
import pandas as pd
import time
import os

st.set_page_config(page_title="AIYODHA CFO Dashboard", layout="wide")

POLICY_ENGINE_URL = "http://localhost:8001"
AGENT_ID = "Agent_007"
LATENCY_LOG_FILE = "latency.log"

st.title("🛡️ AIYODHA Financial Firewall")

# Sidebar for controls
st.sidebar.header("Controls")

if st.sidebar.button("🚨 EMERGENCY KILL SWITCH", type="primary"):
    try:
        resp = requests.post(f"{POLICY_ENGINE_URL}/admin/kill_switch", params={"agent_id": AGENT_ID})
        if resp.status_code == 200:
            st.sidebar.success("KILL SIGNAL SENT!")
        else:
            st.sidebar.error(f"Failed to send kill signal: {resp.status_code}")
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")

# Main Dashboard
col1, col2 = st.columns(2)

def get_agent_status():
    try:
        resp = requests.get(f"{POLICY_ENGINE_URL}/status/{AGENT_ID}")
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

status = get_agent_status()

with col1:
    st.subheader("Agent Status")
    if status:
        st.metric("Budget", f"${status.get('budget', 0.0):.2f}")
        st.metric("Spent", f"${status.get('spent', 0.0):.4f}")
        
        is_killed = status.get("killed", False)
        if is_killed:
            st.error("STATUS: KILLED 💀")
        else:
            st.success("STATUS: ACTIVE 🟢")
    else:
        st.warning("Policy Engine Unreachable")

with col2:
    st.subheader("Latency Overhead (<5ms)")
    if os.path.exists(LATENCY_LOG_FILE):
        try:
            # Read last 100 lines
            with open(LATENCY_LOG_FILE, "r") as f:
                lines = f.readlines()
                data = [float(line.strip()) for line in lines if line.strip()]
                if data:
                    df = pd.DataFrame(data[-100:], columns=["Overhead (ms)"])
                    st.line_chart(df)
                    avg_latency = sum(data) / len(data)
                    st.metric("Avg Overhead", f"{avg_latency:.4f} ms")
        except Exception as e:
            st.error(f"Error reading log: {e}")
    else:
        st.info("Waiting for latency data...")

# Auto-refresh
time.sleep(0.5)
st.rerun()
