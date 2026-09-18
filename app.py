import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Sentinel - Financial & Lifestyle Tracker",
    page_icon="🛡️",
    layout="wide"
)

# --- INITIALIZE SESSION STATE ---
if "transactions" not in st.session_state:
    st.session_state.transactions = []

# --- SIDEBAR & API CONFIGURATION ---
st.sidebar.title("🛡️ Sentinel Controls")
api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Enter your Google AI Studio API key")

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Monthly Budget Targets")
LIFESTYLE_CAP = st.sidebar.number_input("Lifestyle Cap (₹)", value=10000, step=500)
PETROL_CAP = st.sidebar.number_input("Petrol / Commute Cap (₹)", value=3000, step=500)
MONTHLY_SURPLUS = st.sidebar.number_input("Target Monthly Surplus (₹)", value=8832, step=500)

# --- SYSTEM PROMPT FOR GEMINI ---
SYSTEM_PROMPT = """
You are the transaction extraction engine for Sentinel.
Parse the incoming text (SMS, payment notification, or manual log) into a structured JSON object.

Categorization Rules:
1. Category:
   - "Lifestyle": Food, Dining, Drinks, Social, Cigarettes, Tobacco, Grooming, Travel/Vacation.
   - "Commute": Bike fuel, Petrol, Cab, Auto, Metro, Parking.
   - "Card Payoff": Direct payments made towards ICICI, Axis, or OneCard bills.
   - "Fixed/Utility": Bills, Rent, Groceries, WiFi, Electricity.
2. Sub-Category:
   - Food/Dining, Drinks/Alcohol, Cigarettes, Grooming, Bike Petrol, Public Transport, Card Payment, General.
3. Payment Method:
   - Extract explicitly if mentioned: ICICI, Axis, OneCard, UPI, Cash, Bank Transfer. If unspecified, mark as "Unknown/UPI".

Output must strictly adhere to JSON schema:
{
  "amount": number,
  "currency": "INR",
  "merchant": string,
  "category": string,
  "sub_category": string,
  "payment_method": string,
  "notes": string,
  "travel_details": {
    "is_travel": boolean,
    "mode": string or null,
    "distance_km": number or null
  }
}
"""

def parse_with_gemini(text_input, key):
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
    model="gemini-2.5-flash",  # Or "gemini-2.0-flash"
    contents=prompt,
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

    if submit_btn:
        if not api_key:
            st.error("Please enter your Gemini API Key in the sidebar.")
        elif not user_input.strip():
            st.warning("Please enter text to parse.")
        else:
            with st.spinner("Analyzing transaction..."):
                try:
                    parsed_data = parse_with_gemini(user_input, api_key)
                    
                    # Add timestamp & raw string
                    parsed_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    parsed_data["raw_text"] = user_input
                    
                    st.session_state.transactions.append(parsed_data)
                    st.success(f"Parsed: ₹{parsed_data['amount']} under '{parsed_data['category']}' ({parsed_data['sub_category']}) via {parsed_data['payment_method']}")
                    st.json(parsed_data)
                except Exception as e:
                    st.error(f"Error parsing data: {e}")

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
    st.subheader("All Logged Transactions")
    if st.session_state.transactions:
        df_hist = pd.DataFrame(st.session_state.transactions)
        
        # Display clean table
        st.dataframe(
            df_hist[["timestamp", "merchant", "amount", "category", "sub_category", "payment_method", "raw_text"]],
            use_container_width=True
        )
        
        if st.button("🗑️ Clear All Data"):
            st.session_state.transactions = []
            st.rerun()
    else:
        st.write("No transaction history available.")
