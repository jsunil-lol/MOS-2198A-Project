"""Supplier Rescue AI — Streamlit app entry point.

Placeholder home page. Features are built in later steps:
  1. Email received  -> extract delay details with Claude
  2. Impact          -> find affected customer orders
  3. Options         -> compare alternative suppliers
  4. Recommendation  -> AI-written recovery plan
"""

import anthropic
import streamlit as st

import claude_client

st.set_page_config(page_title="Supplier Rescue AI", page_icon="🛟", layout="wide")

st.title("🛟 Supplier Rescue AI")
st.subheader("When a supplier fails to deliver, figure out what to do next.")

st.write(
    "Upload or paste a supplier delay email. Supplier Rescue AI finds the affected "
    "customer orders, compares alternative suppliers, and recommends the most "
    "cost-effective recovery strategy."
)

st.divider()

steps = [
    ("1. Email received", "Read the supplier's delay notice."),
    ("2. Impact", "Find which customer orders are affected."),
    ("3. Options", "Compare alternative suppliers on cost and lead time."),
    ("4. Recommendation", "Get a plain-English recovery plan."),
]
cols = st.columns(len(steps))
for col, (title, desc) in zip(cols, steps):
    with col:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(desc)
            st.caption("_Coming soon_")

st.divider()

# --- Sidebar: Claude API status ---------------------------------------------
with st.sidebar:
    st.header("Settings")
    st.caption(f"Model: `{claude_client.MODEL}`")

    if claude_client.has_api_key():
        st.success("API key found in .env")
        if st.button("Test Claude connection"):
            with st.spinner("Contacting Claude..."):
                try:
                    reply = claude_client.test_connection()
                    st.success(reply or "Connected.")
                except anthropic.AuthenticationError:
                    st.error("API key was rejected. Check ANTHROPIC_API_KEY in .env.")
                except anthropic.APIConnectionError:
                    st.error("Couldn't reach the Claude API. Check your internet connection.")
                except anthropic.APIStatusError as e:
                    st.error(f"Claude API error ({e.status_code}): {e.message}")
    else:
        st.warning("No API key yet. Add ANTHROPIC_API_KEY to the .env file, then restart.")

st.caption(
    "Class prototype. All suppliers, orders, and costs are fictional demonstration data."
)
