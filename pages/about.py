"""
Flight Fare Finder — About Page

Displays information about the application, its APIs, and the POS comparison
strategy.  This page is automatically picked up by Streamlit's multi-page
routing when placed in the ``pages/`` directory.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="About",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("ℹ️ About Flight Fare Finder")

st.markdown(
    "<p style='color: gray; font-size: 1.1em;'>"
    "A smart flight search tool that compares prices across multiple "
    "Point-of-Sale (POS) countries to find the cheapest tickets."
    "</p>",
    unsafe_allow_html=True,
)

st.divider()

# ---------------------------------------------------------------------------
# What is this app?
# ---------------------------------------------------------------------------
st.header("What is this app?")

st.markdown(
    """
    This application helps you find the cheapest flight tickets by comparing
    prices across different **Point-of-Sale (POS)** countries. Airlines
    sometimes price tickets differently depending on which country you appear
    to be booking from — a practice known as **price discrimination by
    market**.

    By searching multiple POS markets simultaneously and converting all prices
    to a single currency (EUR), you can easily identify the cheapest booking
    market and potentially save hundreds on your next trip.
    """
)

st.divider()

# ---------------------------------------------------------------------------
# How it works
# ---------------------------------------------------------------------------
st.header("How it works")

steps: list[tuple[str, str]] = [
    (
        "📝 Enter your flight search criteria",
        "Provide your origin, destination, dates, passengers, and preferred cabin class.",
    ),
    (
        "🌍 Select countries to compare",
        "Choose from 15 pre-configured POS countries. Each country represents a different pricing market.",
    ),
    (
        "🔍 The app searches each country's market",
        "For each selected country, the Amadeus API is queried with that country's local currency.",
    ),
    (
        "💶 Prices are converted to EUR",
        "All prices are normalized to EUR using real-time exchange rates for fair comparison.",
    ),
    (
        "📊 Filter, sort, and export",
        "Use the interactive dashboard to find your ideal flight and export results to CSV or Excel.",
    ),
]

for i, (title, description) in enumerate(steps, start=1):
    col1, col2 = st.columns([1, 10])
    with col1:
        st.markdown(f"<h2 style='text-align:center'>{i}</h2>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**{title}**  \n{description}")

st.divider()

# ---------------------------------------------------------------------------
# APIs Used
# ---------------------------------------------------------------------------
st.header("APIs Used")

api_col1, api_col2, api_col3 = st.columns(3)

with api_col1:
    st.info(
        "**Amadeus Flight Offers Search API**\n\n"
        "Primary data source for flight search. Provides real-time flight "
        "offers from airlines worldwide. Free tier available with generous "
        "rate limits.\n\n"
        "🔗 [developers.amadeus.com](https://developers.amadeus.com)"
    )

with api_col2:
    st.info(
        "**Exchange Rate API**\n\n"
        "Real-time currency conversion used to normalize all prices to EUR. "
        "Uses a free-tier endpoint with no API key required for basic "
        "currency pairs.\n\n"
        "🔗 [exchangerate-api.com](https://www.exchangerate-api.com)"
    )

with api_col3:
    st.info(
        "**Travelpayouts API** *(optional)*\n\n"
        "Provides historical price trends and price prediction data to help "
        "you decide the best time to book.\n\n"
        "🔗 [travelpayouts.com](https://www.travelpayouts.com/developers/api)"
    )

st.divider()

# ---------------------------------------------------------------------------
# POS Strategy
# ---------------------------------------------------------------------------
st.header("POS Comparison Strategy")

st.markdown(
    """
    The app uses **currency-based POS comparison**. For each selected country,
    the Amadeus API is called with that country's local currency code. Airlines
    and travel agencies often set different base fares per market, which means
    the same flight can have different prices when queried in different
    currencies.

    **Example workflow:**
    """
)

st.code(
    """
1. Search Finland (FI)  → Price: €185.00 EUR
2. Search Turkey (TR)   → Price: €162.50 EUR (converted from TRY)
3. Search India (IN)    → Price: €178.20 EUR (converted from INR)
4. Search Brazil (BR)   → Price: €191.00 EUR (converted from BRL)

→ Best price: Turkey at €162.50 (save €22.50 vs Finland!)
    """.strip(),
    language="text",
)

st.markdown(
    """
    This approach effectively simulates browsing and booking from different
    countries, which is a well-known strategy for finding lower airfares.
    All results are displayed in EUR so you can compare apples to apples.
    """
)

st.divider()

# ---------------------------------------------------------------------------
# Getting Started
# ---------------------------------------------------------------------------
st.header("Getting Started")

st.markdown(
    """
    Follow these steps to run the app locally:

    **1. Get your free Amadeus API key**
    - Visit [developers.amadeus.com/register](https://developers.amadeus.com/register)
    - Create a free account
    - Generate your API key and secret from the dashboard

    **2. Clone the repository and install dependencies**
    ```bash
    git clone https://github.com/mozy1312/flight-fare-comparison.git
    cd flight-fare-comparison
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

    **3. Configure environment variables**
    ```bash
    cp .env.example .env
    # Edit .env and add your Amadeus credentials
    ```

    **4. Launch the app**
    ```bash
    streamlit run app.py
    ```
    """
)

st.divider()

# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------
st.caption(
    "**Disclaimer:** Prices shown are indicative and sourced from third-party "
    "APIs. Actual booking prices may differ. Always verify the final price "
    "on the airline's official website or authorized booking platform before "
    "making a purchase. This application does not process payments or bookings."
)
