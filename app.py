"""Supplier Rescue AI — Streamlit app entry point.

Placeholder home page. Features are built in later steps:
  1. Email received  -> extract delay details with Claude
  2. Impact          -> find affected customer orders
  3. Options         -> compare alternative suppliers
  4. Recommendation  -> AI-written recovery plan
"""

from pathlib import Path

import anthropic
import streamlit as st

import claude_client
from supplier_delay import FIELD_LABELS, ExtractionError, extract_supplier_delay

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

# --- Step 1: Email received --------------------------------------------------
SAMPLE_EMAIL_PATH = Path(__file__).parent / "data" / "sample_delay_email.txt"

st.header("1. Email received")

if st.button("Load sample email", disabled=not SAMPLE_EMAIL_PATH.exists()):
    st.session_state.email_text = SAMPLE_EMAIL_PATH.read_text()
    st.session_state.pop("extraction", None)
    st.session_state.pop("confirmed_delay", None)

email_text = st.text_area(
    "Paste the supplier's delay email",
    key="email_text",
    height=260,
)

if st.button("Extract delay details", type="primary", disabled=not email_text.strip()):
    st.session_state.pop("confirmed_delay", None)
    with st.spinner("Claude is reading the email..."):
        try:
            st.session_state.extraction = extract_supplier_delay(email_text)
            st.session_state.extraction_error = None
        except ExtractionError as e:
            st.session_state.extraction = None
            st.session_state.extraction_error = str(e)

if st.session_state.get("extraction_error"):
    st.error(st.session_state.extraction_error)

extraction = st.session_state.get("extraction")
if extraction is not None:
    if extraction.complete:
        st.success("All four details were found. Check them, then confirm.")
    else:
        names = ", ".join(FIELD_LABELS[f] for f in extraction.missing)
        st.warning(f"Missing or unclear: **{names}**. Fill these in before confirming.")
    for note in extraction.notes:
        st.caption(f"⚠️ {note}")

    def flag(field: str) -> str:
        return " ⚠️" if field in extraction.missing else ""

    with st.form("confirm_delay"):
        c1, c2, c3, c4 = st.columns(4)
        po = c1.text_input(FIELD_LABELS["po_number"] + flag("po_number"),
                           value=extraction.po_number or "")
        part = c2.text_input(FIELD_LABELS["part_number"] + flag("part_number"),
                             value=extraction.part_number or "")
        qty = c3.number_input(FIELD_LABELS["quantity"] + flag("quantity"),
                              value=extraction.quantity, min_value=1, step=1)
        arrival = c4.date_input(FIELD_LABELS["revised_arrival_on"] + flag("revised_arrival_on"),
                                value=extraction.revised_arrival_on, format="YYYY-MM-DD")
        confirmed = st.form_submit_button("Confirm details")

    if confirmed:
        if not (po.strip() and part.strip() and qty and arrival):
            st.error("Fill in all four details before confirming.")
        else:
            st.session_state.confirmed_delay = {
                "po_number": po.strip(),
                "part_number": part.strip(),
                "quantity": int(qty),
                "revised_arrival_on": arrival,
            }

confirmed_delay = st.session_state.get("confirmed_delay")
if confirmed_delay:
    st.success(
        f"Confirmed: {confirmed_delay['quantity']} × {confirmed_delay['part_number']} "
        f"on {confirmed_delay['po_number']}, now arriving "
        f"{confirmed_delay['revised_arrival_on']:%Y-%m-%d}. "
        "Ready for the order-impact calculations."
    )

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
