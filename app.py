import streamlit as st
import json
import pandas as pd
from google import genai
from google.genai import types
from supabase import create_client, Client

# --- SYSTEM PROMPT DEFINITION ---
SYSTEM_PROMPT = """
You are Sentinel, an AI financial parser. Extract structured transaction details from payment SMS or user logs.
Return ONLY a valid JSON object with no markdown formatting or extra text, matching this structure:
{
    "amount": number or null,
    "category": string (e.g., "Commute / Petrol", "Food & Dining", "Bills", "Lifestyle", "Uncategorized"),
    "merchant": string or null,
    "payment_method": string or null (e.g., "ICICI", "Axis", "OneCard", "UPI", "Cash"),
    "notes": string or null,
    "travel_details": {
        "is_travel": boolean,
        "mode": string or null,
        "distance_km": number or null
    }
}
"""

# --- SUPABASE DATABASE CONNECTION ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def fetch_transactions():
    try:
        response = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

def save_transaction(parsed_data, raw_text):
    travel_info = parsed_data.get("travel_details", {}) or {}
    record = {
        "raw_text": raw_text,
        "amount": parsed_data.get("amount", 0),
        "category": parsed_data.get("category", "Uncategorized"),
        "merchant": parsed_data.get("merchant", ""),
        "payment_method": parsed_data.get("payment_method", ""),
        "notes": parsed_data.get("notes", ""),
        "is_travel": travel_info.get("is_travel", False),
        "distance_km": travel_info.get("distance_km", 0)
    }
    supabase.table("transactions").insert(record).execute()

# --- GEMINI AI PARSER ---
def parse_with_gemini(text_input, key):
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=text_input,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    return json.loads(response.text)

# --- MAIN APP HEADER ---
st.title("🛡️ Sentinel: Spending & Habit Tracker")
st.caption("AI-Powered Transaction Parser & Budget Compliance Engine")

# --- TAB NAVIGATION ---
tab_input, tab_dash, tab_history = st.tabs(["📥 Log Transaction / SMS", "📊 Budget Dashboard", "📋 Transaction History"])

# ==========================================
# TAB 1: INPUT & SMS PARSER
# ==========================================
with tab_input:
    st.subheader("Parse Payment SMS or Quick Log")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        user_input = st.text_area(
            "Paste SMS or Type Log",
            placeholder="e.g., 'Paid Rs 450 at Taproom using Axis card' or 'Filled 300 petrol in bike via UPI' or 'Bought Marlboro 180 OneCard'",
            height=120
        )
        submit_btn = st.button("🚀 Process with Gemini AI", type="primary")

    with col2:
        st.info("""
        **Quick Examples to Try:**
        - `Spent Rs 250 on lunch at McD using ICICI`
        - `Filled petrol Rs 500 bike travel 40km UPI`
        - `Paid 1499 to OneCard bill via NetBanking`
        - `Cigarettes and tea Rs 120 Cash`
        """)

# Ensure api_key is retrieved from Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY", "")

with tab_input:
    st.subheader("Parse Payment SMS or Quick Log")
    user_input = st.text_area("Paste SMS or Type Log", placeholder="e.g., 'Paid Rs 450 at Taproom using Axis card'", height=120)
    submit_btn = st.button("🚀 Process with Gemini AI", type="primary", key="process_gemini_btn")

    if submit_btn and user_input:
        if not api_key:
            st.error("GEMINI_API_KEY is missing in Streamlit Secrets!")
        else:
            with st.spinner("Processing transaction..."):
                try:
                    parsed = parse_with_gemini(user_input, api_key)
                    save_transaction(parsed, user_input)
                    st.success("Transaction parsed and saved to Supabase permanently!")
                    st.json(parsed)
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# TAB 2: DASHBOARD & BUDGET METRICS
# ==========================================
with tab_dash:
    if not st.session_state.transactions:
        st.info("No transactions logged yet. Use the first tab to add SMS inputs.")
    else:
        df = pd.DataFrame(st.session_state.transactions)
        
        # Calculate key metrics
        lifestyle_spent = df[df["category"] == "Lifestyle"]["amount"].sum() if "category" in df else 0
        commute_spent = df[df["category"] == "Commute"]["amount"].sum() if "category" in df else 0
        card_repayments = df[df["category"] == "Card Payoff"]["amount"].sum() if "category" in df else 0
        
        # Metric Cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Lifestyle Spent", f"₹{lifestyle_spent:,.0f}", f"Target: ₹{LIFESTYLE_CAP:,.0f}", delta_color="inverse")
        m2.metric("Commute/Petrol Spent", f"₹{commute_spent:,.0f}", f"Target: ₹{PETROL_CAP:,.0f}", delta_color="inverse")
        m3.metric("Card Debt Repaid", f"₹{card_repayments:,.0f}")
        m4.metric("Target Surplus", f"₹{MONTHLY_SURPLUS:,.0f}", "Monthly Goal")

        st.markdown("---")
        
        # Progress Bars
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            ls_ratio = min(lifestyle_spent / LIFESTYLE_CAP, 1.0)
            st.write(f"**Lifestyle Budget Used ({ls_ratio*100:.1f}%)**")
            st.progress(ls_ratio)
            if lifestyle_spent > LIFESTYLE_CAP:
                st.error("🚨 Warning: Lifestyle budget limit exceeded!")
                
        with col_p2:
            petrol_ratio = min(commute_spent / PETROL_CAP, 1.0)
            st.write(f"**Commute/Petrol Budget Used ({petrol_ratio*100:.1f}%)**")
            st.progress(petrol_ratio)

        st.markdown("---")
        
        # Visual Breakdown Charts
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Sub-Category Breakdown (Micro-Habits)")
            fig_sub = px.pie(df, names="sub_category", values="amount", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_sub, use_container_width=True)

        with c2:
            st.subheader("Payment Method Distribution")
            fig_pay = px.bar(df, x="payment_method", y="amount", color="category", barmode="stack", color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pay, use_container_width=True)

# ==========================================
# TAB 3: TRANSACTION HISTORY
# ==========================================
with tab_history:
    st.subheader("Transaction History")
    records = fetch_transactions()
    if records:
        df = pd.DataFrame(records)
        # Select columns that exist in the dataframe
        display_cols = [col for col in ["created_at", "raw_text", "amount", "category", "merchant", "payment_method", "notes"] if col in df.columns]
        st.dataframe(df[display_cols], use_container_width=True)
    else:
        st.info("No saved transactions found in Supabase yet.")
