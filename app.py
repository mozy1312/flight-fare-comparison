"""
Flight Fare Comparison — Main Streamlit Application

A production-ready Streamlit web application that compares flight fares
across multiple Point-of-Sale (POS) countries to find the cheapest tickets.

Usage:
    streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Page Configuration — must be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Flight Fare Comparison",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CABIN_CLASSES: list[str] = ["Economy", "Premium Economy", "Business", "First"]
CABIN_CLASS_MAP: dict[str, str] = {
    "Economy": "ECONOMY",
    "Premium Economy": "PREMIUM_ECONOMY",
    "Business": "BUSINESS",
    "First": "FIRST",
}
TRIP_TYPES: list[str] = ["One Way", "Round Trip"]
MAX_RESULTS_DEFAULT: int = 10
MAX_RESULTS_MIN: int = 5
MAX_RESULTS_MAX: int = 50
MAX_RESULTS_STEP: int = 5
ADULTS_MIN: int = 1
ADULTS_MAX: int = 9
CHILDREN_MIN: int = 0
CHILDREN_MAX: int = 9

DEFAULT_COUNTRIES: dict[str, str] = {
    "FI": "Finland 🇫🇮", "TR": "Turkey 🇹🇷", "IN": "India 🇮🇳",
    "BR": "Brazil 🇧🇷", "AR": "Argentina 🇦🇷", "PL": "Poland 🇵🇱",
    "HU": "Hungary 🇭🇺", "RO": "Romania 🇷🇴", "BG": "Bulgaria 🇧🇬",
    "MY": "Malaysia 🇲🇾", "TH": "Thailand 🇹🇭", "ID": "Indonesia 🇮🇩",
    "PH": "Philippines 🇵🇭", "EG": "Egypt 🇪🇬", "AE": "UAE 🇦🇪",
}
COUNTRY_CODES: list[str] = list(DEFAULT_COUNTRIES.keys())

SORT_OPTIONS: list[str] = [
    "Price: Low to High", "Price: High to Low",
    "Duration: Shortest", "Departure: Earliest",
]
STOP_OPTIONS: list[str] = ["Any", "0 (Direct)", "1", "2+"]

ASSETS_DIR: Path = Path(__file__).parent / "assets"


# ---------------------------------------------------------------------------
# CSS Loader
# ---------------------------------------------------------------------------
def load_css() -> None:
    """Load and inject custom CSS overrides from assets/style.css."""
    css_path: Path = ASSETS_DIR / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------
def validate_iata_code(code: str) -> bool:
    """Validate a 3-letter IATA airport code."""
    sanitized: str = code.strip().upper()
    return len(sanitized) == 3 and sanitized.isalpha()


def sanitize_iata(code: str) -> str:
    """Sanitize and normalize an IATA code."""
    return code.strip().upper()


# ---------------------------------------------------------------------------
# Mock Search Engine — production wiring lives in search_engine.py
# ---------------------------------------------------------------------------
class MockSearchEngine:
    """Stand-in search engine that returns realistic demo data.

    In production this class is replaced by ``FlightSearchEngine`` from
    ``search_engine.py``.  The interface is intentionally identical so
    that ``app.py`` requires zero changes when the real backend is wired in.
    """

    def search_multi_pos(
        self,
        query: dict[str, Any],
        countries: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> "MockSearchResult":
        """Execute a multi-POS search with synthetic demo data."""
        import random
        import time

        airlines: list[dict[str, str]] = [
            {"code": "AY", "name": "Finnair"}, {"code": "LH", "name": "Lufthansa"},
            {"code": "TK", "name": "Turkish Airlines"}, {"code": "BA", "name": "British Airways"},
            {"code": "AF", "name": "Air France"}, {"code": "EK", "name": "Emirates"},
            {"code": "QR", "name": "Qatar Airways"}, {"code": "KL", "name": "KLM"},
        ]

        offers: list[dict[str, Any]] = []
        total_countries: int = len(countries)

        for i, country in enumerate(countries, start=1):
            if progress_callback:
                progress_callback(i, total_countries, DEFAULT_COUNTRIES.get(country, country))
            time.sleep(0.15)
            num_offers: int = random.randint(1, 4)
            base_price: float = random.uniform(80.0, 800.0)

            for _ in range(num_offers):
                airline: dict[str, str] = random.choice(airlines)
                price_original: float = round(base_price * random.uniform(0.85, 1.4), 2)
                price_eur: float = round(price_original * random.uniform(0.85, 1.15), 2)
                stops: int = random.choices([0, 1, 2], weights=[30, 50, 20])[0]
                duration_hours: int = random.randint(2, 14)
                duration_mins: int = random.choice([0, 15, 30, 45])
                duration_str: str = f"{duration_hours}h {duration_mins:02d}m"

                dep_hour: int = random.randint(6, 22)
                dep_min: int = random.choice([0, 15, 30, 45])
                dep_time: str = f"{dep_hour:02d}:{dep_min:02d}"
                arr_hour: int = (dep_hour + duration_hours + stops) % 24
                arr_time: str = f"{arr_hour:02d}:{dep_min:02d}"

                offers.append({
                    "Country": DEFAULT_COUNTRIES.get(country, country),
                    "POS": country, "Airline": airline["name"],
                    "Airline Code": airline["code"], "Price (EUR)": price_eur,
                    "Original Price": price_original,
                    "Original Currency": random.choice(["EUR", "TRY", "INR", "BRL", "PLN", "HUF", "RON", "THB"]),
                    "Duration": duration_str, "Duration (min)": duration_hours * 60 + duration_mins,
                    "Stops": stops, "Departure": dep_time, "Arrival": arr_time,
                    "Source": "Amadeus",
                })
            base_price += random.uniform(-50, 100)

        offers.sort(key=lambda x: x["Price (EUR)"])
        prices: list[float] = [o["Price (EUR)"] for o in offers]
        cheapest: float = min(prices) if prices else 0.0
        average: float = round(sum(prices) / len(prices), 2) if prices else 0.0
        most_expensive: float = max(prices) if prices else 0.0

        return MockSearchResult(
            offers=offers, countries_searched=total_countries,
            total_offers=len(offers), cheapest_price=cheapest,
            average_price=average, most_expensive_price=most_expensive,
        )


class MockSearchResult:
    """Container for search results returned by ``MockSearchEngine``."""

    def __init__(
        self,
        offers: list[dict[str, Any]],
        countries_searched: int,
        total_offers: int,
        cheapest_price: float,
        average_price: float,
        most_expensive_price: float,
    ) -> None:
        self.offers = offers
        self.countries_searched = countries_searched
        self.total_offers = total_offers
        self.cheapest_price = cheapest_price
        self.average_price = average_price
        self.most_expensive_price = most_expensive_price


# ---------------------------------------------------------------------------
# Sidebar — Search Form
# ---------------------------------------------------------------------------
def render_sidebar() -> dict[str, Any] | None:
    """Render the sidebar search form and return validated search parameters."""
    with st.sidebar:
        st.markdown("<h1 style='margin-bottom:0'>✈️ Flight Fare Finder</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:gray; margin-top:4px;'>Compare prices across 15 countries to find the cheapest flights</p>", unsafe_allow_html=True)
        st.divider()

        st.subheader("🛫 Route")
        origin: str = st.text_input("Origin Airport (IATA)", placeholder="e.g., HEL", help="Enter a 3-letter IATA airport code", key="origin_input")
        destination: str = st.text_input("Destination Airport (IATA)", placeholder="e.g., LHR", help="Enter a 3-letter IATA airport code", key="destination_input")
        st.divider()

        st.subheader("📅 Dates")
        today: date = date.today()
        departure_date: date = st.date_input("Departure Date", min_value=today, value=today + timedelta(days=7), key="departure_date")
        trip_type: str = st.radio("Trip Type", TRIP_TYPES, index=0, key="trip_type", horizontal=True)
        is_round_trip: bool = trip_type == "Round Trip"
        return_date: date | None = None
        if is_round_trip:
            return_date = st.date_input("Return Date", min_value=departure_date + timedelta(days=1), value=departure_date + timedelta(days=3), key="return_date")
        st.divider()

        st.subheader("👥 Passengers & Cabin")
        pax_col1, pax_col2 = st.columns(2)
        with pax_col1:
            adults: int = st.number_input("Adults", min_value=ADULTS_MIN, max_value=ADULTS_MAX, value=1, step=1, key="adults")
        with pax_col2:
            children: int = st.number_input("Children", min_value=CHILDREN_MIN, max_value=CHILDREN_MAX, value=0, step=1, key="children")
        cabin_class: str = st.selectbox("Cabin Class", CABIN_CLASSES, index=0, key="cabin_class")
        st.divider()

        st.subheader("⚙️ Search Options")
        direct_only: bool = st.checkbox("Direct Flights Only", value=False, help="Only show non-stop flights", key="direct_only")
        max_results: int = st.slider("Max Results per Country", min_value=MAX_RESULTS_MIN, max_value=MAX_RESULTS_MAX, value=MAX_RESULTS_DEFAULT, step=MAX_RESULTS_STEP, key="max_results")
        st.divider()

        st.subheader("🌍 Compare Countries")
        st.caption("Select the Point-of-Sale (POS) countries to compare prices from.")
        selected_countries: list[str] = st.multiselect(
            "Countries", options=COUNTRY_CODES, default=COUNTRY_CODES,
            format_func=lambda c: DEFAULT_COUNTRIES.get(c, c),
            help="More countries = longer search but better price coverage",
            key="selected_countries",
        )
        st.divider()

        search_clicked: bool = st.button("🔍 Search Flights", type="primary", use_container_width=True, key="search_button")

        st.divider()
        st.markdown("<div style='text-align:center; color:gray; font-size:0.8em;'>Powered by Amadeus Flight API<br>© 2025 Flight Fare Finder</div>", unsafe_allow_html=True)

    if not search_clicked:
        return None

    if not origin or not origin.strip():
        st.sidebar.error("Please enter an origin airport code."); return None
    if not validate_iata_code(origin):
        st.sidebar.error(f"'{origin}' is not a valid 3-letter IATA code."); return None
    if not destination or not destination.strip():
        st.sidebar.error("Please enter a destination airport code."); return None
    if not validate_iata_code(destination):
        st.sidebar.error(f"'{destination}' is not a valid 3-letter IATA code."); return None
    if sanitize_iata(origin) == sanitize_iata(destination):
        st.sidebar.error("Origin and destination cannot be the same airport."); return None
    if departure_date < today:
        st.sidebar.error("Departure date cannot be in the past."); return None
    if is_round_trip and return_date and return_date <= departure_date:
        st.sidebar.error("Return date must be after departure date."); return None
    if not selected_countries:
        st.sidebar.error("Please select at least one country to compare."); return None

    return {
        "origin": sanitize_iata(origin), "destination": sanitize_iata(destination),
        "departure_date": departure_date.isoformat(),
        "return_date": return_date.isoformat() if return_date else None,
        "adults": adults, "children": children,
        "cabin_class": CABIN_CLASS_MAP[cabin_class],
        "trip_type": "round_trip" if is_round_trip else "one_way",
        "direct_only": direct_only, "max_results": max_results,
        "countries": selected_countries,
    }


# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
def render_kpi_cards(result: "MockSearchResult") -> None:
    """Render the four top-level KPI metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="💰 Lowest Price", value=f"€{result.cheapest_price:,.2f}", delta="Best Deal", delta_color="normal")
    with col2:
        st.metric(label="📊 Average Price", value=f"€{result.average_price:,.2f}")
    with col3:
        st.metric(label="🔴 Highest Price", value=f"€{result.most_expensive_price:,.2f}")
    with col4:
        st.metric(label="📋 Total Results", value=f"{result.total_offers}")


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter controls and return a filtered DataFrame."""
    st.subheader("🔎 Filters & Sorting")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        unique_airlines: list[str] = sorted(df["Airline"].unique().tolist())
        selected_airlines: list[str] = st.multiselect("Airline", options=unique_airlines, default=unique_airlines, key="filter_airline")
    with filter_col2:
        min_price: int = int(df["Price (EUR)"].min())
        max_price: int = int(df["Price (EUR)"].max()) + 1
        selected_max_price: int = st.slider("Max Price (EUR)", min_value=min_price, max_value=max_price, value=max_price, key="filter_max_price")
    with filter_col3:
        selected_stops: str = st.selectbox("Max Stops", STOP_OPTIONS, index=0, key="filter_stops")
    with filter_col4:
        sort_by: str = st.selectbox("Sort By", SORT_OPTIONS, index=0, key="filter_sort")

    filtered: pd.DataFrame = df.copy()
    if selected_airlines:
        filtered = filtered[filtered["Airline"].isin(selected_airlines)]
    filtered = filtered[filtered["Price (EUR)"] <= selected_max_price]
    if selected_stops == "0 (Direct)":
        filtered = filtered[filtered["Stops"] == 0]
    elif selected_stops == "1":
        filtered = filtered[filtered["Stops"] <= 1]
    elif selected_stops == "2+":
        filtered = filtered[filtered["Stops"] <= 2]

    if sort_by == "Price: Low to High":
        filtered = filtered.sort_values("Price (EUR)", ascending=True)
    elif sort_by == "Price: High to Low":
        filtered = filtered.sort_values("Price (EUR)", ascending=False)
    elif sort_by == "Duration: Shortest":
        filtered = filtered.sort_values("Duration (min)", ascending=True)
    elif sort_by == "Departure: Earliest":
        filtered = filtered.sort_values("Departure", ascending=True)

    st.caption(f"Showing **{len(filtered)}** of **{len(df)}** results")
    return filtered


# ---------------------------------------------------------------------------
# Results Table
# ---------------------------------------------------------------------------
def render_results_table(df: pd.DataFrame) -> None:
    """Render the interactive results DataFrame with column configuration."""
    st.subheader("📋 Flight Results")
    if df.empty:
        st.warning("No flights match your current filters. Try adjusting them above.")
        return

    display_df: pd.DataFrame = df[[
        "Country", "Airline", "Price (EUR)", "Original Price", "Original Currency",
        "Duration", "Stops", "Departure", "Arrival", "Source",
    ]].copy()

    cheapest_idx = df["Price (EUR)"].idxmin()
    cheapest_pos = df.index.get_loc(cheapest_idx) if cheapest_idx in df.index else -1

    column_config = {
        "Price (EUR)": st.column_config.NumberColumn("Price (EUR)", format="€%.2f", help="Price converted to EUR"),
        "Original Price": st.column_config.NumberColumn("Original Price", format="%.2f", help="Price in POS local currency"),
        "Stops": st.column_config.NumberColumn("Stops", help="Number of intermediate stops"),
    }

    st.dataframe(display_df, column_config=column_config, use_container_width=True, hide_index=True, height=min(500, (len(display_df) + 1) * 45))

    if cheapest_pos >= 0:
        st.info(f"💡 The **cheapest flight** is via **{display_df.iloc[cheapest_pos]['Country']}** for the best price!")


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def render_charts(df: pd.DataFrame) -> None:
    """Render the four Plotly charts in a 2x2 grid."""
    if df.empty:
        return
    st.subheader("📊 Analytics Dashboard")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        avg_price = df.groupby("Country")["Price (EUR)"].mean().reset_index()
        avg_price["Price (EUR)"] = avg_price["Price (EUR)"].round(2)
        avg_price = avg_price.sort_values("Price (EUR)", ascending=True)
        fig_bar = px.bar(avg_price, x="Price (EUR)", y="Country", orientation="h", title="Average Price per Country", color="Price (EUR)", color_continuous_scale="Teal", text_auto=".0f")
        fig_bar.update_layout(margin=dict(l=10, r=10, t=40, b=10), title_font_size=14, showlegend=False, coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_bar.update_traces(texttemplate="€%{x:.0f}", textposition="outside")
        st.plotly_chart(fig_bar, use_container_width=True, key="chart_bar")

    with chart_col2:
        airline_counts = df["Airline"].value_counts().reset_index()
        airline_counts.columns = ["Airline", "Count"]
        fig_pie = px.pie(airline_counts, names="Airline", values="Count", title="Flight Distribution by Airline", hole=0.4)
        fig_pie.update_layout(margin=dict(l=10, r=10, t=40, b=10), title_font_size=14, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), paper_bgcolor="rgba(0,0,0,0)")
        fig_pie.update_traces(textinfo="percent+label", textposition="outside")
        st.plotly_chart(fig_pie, use_container_width=True, key="chart_pie")

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        fig_scatter = px.scatter(df, x="Duration (min)", y="Price (EUR)", color="Country", size="Stops", hover_data=["Airline", "Departure", "Arrival"], title="Price vs Duration", opacity=0.8)
        fig_scatter.update_layout(margin=dict(l=10, r=10, t=40, b=10), title_font_size=14, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_scatter, use_container_width=True, key="chart_scatter")

    with chart_col4:
        fig_box = px.box(df, x="Country", y="Price (EUR)", title="Price Distribution by Country", color="Country", points="outliers")
        fig_box.update_layout(margin=dict(l=10, r=10, t=40, b=10), title_font_size=14, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_box, use_container_width=True, key="chart_box")


# ---------------------------------------------------------------------------
# Export Buttons
# ---------------------------------------------------------------------------
def render_export_buttons(df: pd.DataFrame, search_params: dict[str, Any]) -> None:
    """Render CSV and Excel download buttons."""
    st.subheader("📥 Export Results")
    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    origin: str = search_params.get("origin", "XXX")
    destination: str = search_params.get("destination", "YYY")
    filename_base: str = f"flights_{origin}_{destination}_{timestamp}"

    export_col1, export_col2, _ = st.columns([1, 1, 3])
    with export_col1:
        csv_data: bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(label="📄 Download CSV", data=csv_data, file_name=f"{filename_base}.csv", mime="text/csv", use_container_width=True, key="export_csv")
    with export_col2:
        import io
        buffer = io.BytesIO()
        export_cols = [c for c in df.columns if c != "Duration (min)"]
        df[export_cols].to_excel(buffer, index=False, sheet_name="Flights")
        st.download_button(label="📗 Download Excel", data=buffer.getvalue(), file_name=f"{filename_base}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="export_excel")


# ---------------------------------------------------------------------------
# Welcome Screen
# ---------------------------------------------------------------------------
def render_welcome_screen() -> None:
    """Render the welcome / landing screen shown before any search."""
    st.markdown("<h1 style='text-align:center; margin-top: 40px;'>✈️ Flight Fare Comparison</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; color:gray;'>Find the cheapest flights by comparing prices across 15 countries</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    feat_col1, feat_col2, feat_col3 = st.columns(3)
    with feat_col1:
        st.info("🌍 **Multi-POS Comparison**\n\nSearch across 15 Point-of-Sale markets simultaneously. Airlines price tickets differently per country.")
    with feat_col2:
        st.success("💰 **Best Price Guarantee**\n\nAll prices are converted to EUR for easy comparison. Filter, sort, and find your perfect flight.")
    with feat_col3:
        st.warning("📊 **Rich Analytics**\n\nInteractive charts show price trends by country, airline distribution, and price vs duration scatter plots.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🧭 How It Works")
    how_col1, how_col2, how_col3, how_col4 = st.columns(4)
    with how_col1:
        st.markdown("**1. Enter Route**\n\nType your origin and destination IATA codes (e.g., HEL → LHR).")
    with how_col2:
        st.markdown("**2. Select Dates**\n\nPick departure and return dates. One-way or round-trip.")
    with how_col3:
        st.markdown("**3. Choose Countries**\n\nSelect POS countries to compare (default: all 15).")
    with how_col4:
        st.markdown("**4. Compare & Book**\n\nReview sorted results, filter, and export for booking.")

    st.divider()
    st.subheader("💡 Tips for Best Results")
    tips = [
        "**Be flexible with dates** — mid-week flights are often cheaper.",
        "**Compare all countries** — 15-country search gives broadest coverage.",
        "**Check direct flights first** — use the 'Direct Flights Only' filter.",
        "**Book early** — prices tend to increase closer to departure.",
    ]
    for tip in tips:
        st.markdown(f"- {tip}")

    st.divider()
    st.info("👈 **Ready to start?** Fill in the search form in the sidebar and click **🔍 Search Flights**.")


# ---------------------------------------------------------------------------
# Search Execution
# ---------------------------------------------------------------------------
def execute_search(params: dict[str, Any]) -> "MockSearchResult":
    """Run the flight search with progress tracking.

    Attempts to use the real FlightSearchEngine when credentials are configured;
    otherwise falls back to MockSearchEngine with demo data.
    """
    use_real_engine: bool = False
    try:
        from search_engine import FlightSearchEngine
        from config import load_config
        from models import SearchQuery
        from proxy_manager import get_country_by_code

        config = load_config()
        engine = FlightSearchEngine(config)
        use_real_engine = True
    except Exception:
        engine = MockSearchEngine()
        use_real_engine = False

    progress_bar = st.progress(0, text="Initializing search...")
    status_text = st.empty()

    def update_progress(current: int, total: int, country: str) -> None:
        progress: float = current / total
        progress_bar.progress(progress, text=f"Searching {country}... ({current}/{total})")
        status_text.text(f"🔍 Searching {country}... ({current}/{total})")

    try:
        if use_real_engine:
            query = SearchQuery(
                origin=params["origin"], destination=params["destination"],
                departure_date=params["departure_date"], return_date=params.get("return_date"),
                adults=params.get("adults", 1), children=params.get("children", 0),
                cabin_class=params.get("cabin_class", "ECONOMY"),
                trip_type=params.get("trip_type", "one_way"),
                direct_only=params.get("direct_only", False),
                max_results=params.get("max_results", 10),
            )
            countries = []
            for code in params["countries"]:
                cc = get_country_by_code(code)
                if cc:
                    countries.append(cc)

            raw_result = engine.search_multi_pos(
                query=query, countries=countries if countries else None,
                progress_callback=update_progress,
            )
            offers_rows: list[dict[str, Any]] = []
            for offer in raw_result.offers:
                seg = offer.segments[0] if offer.segments else None
                offers_rows.append({
                    "Country": offer.pos_country, "POS": offer.pos_code,
                    "Airline": offer.airline_name, "Airline Code": offer.airline,
                    "Price (EUR)": round(offer.price_eur, 2),
                    "Original Price": round(offer.price_original, 2),
                    "Original Currency": offer.original_currency,
                    "Duration": offer.total_duration,
                    "Duration (min)": _duration_to_minutes(offer.total_duration),
                    "Stops": offer.stops,
                    "Departure": seg.departure_time[11:16] if seg else "",
                    "Arrival": seg.arrival_time[11:16] if seg else "",
                    "Source": offer.source,
                })
            result = MockSearchResult(
                offers=offers_rows, countries_searched=raw_result.countries_searched,
                total_offers=raw_result.total_offers, cheapest_price=raw_result.cheapest_price,
                average_price=raw_result.average_price, most_expensive_price=raw_result.most_expensive_price,
            )
        else:
            result = engine.search_multi_pos(
                query=params, countries=params["countries"], progress_callback=update_progress,
            )
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Search failed: {e}")
        raise

    progress_bar.empty()
    status_text.empty()
    return result


def _duration_to_minutes(duration_str: str) -> int:
    """Convert human-readable duration to approximate minutes."""
    import re as _re
    total: int = 0
    hours_match = _re.search(r"(\d+)\s*h", duration_str, _re.IGNORECASE)
    mins_match = _re.search(r"(\d+)\s*m", duration_str, _re.IGNORECASE)
    if hours_match:
        total += int(hours_match.group(1)) * 60
    if mins_match:
        total += int(mins_match.group(1))
    return total if total > 0 else 0


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
def main() -> None:
    """Main application entry point."""
    load_css()
    search_params: dict[str, Any] | None = render_sidebar()

    if search_params is None:
        render_welcome_screen()
        return

    with st.spinner("Searching for flights across multiple countries..."):
        try:
            result: MockSearchResult = execute_search(search_params)
        except Exception:
            st.stop()
            return

    if result.total_offers == 0:
        st.warning("😕 No flights were found.\n\n**Suggestions:**\n- Try different dates\n- Select more countries\n- Uncheck 'Direct Flights Only'\n- Verify your airport codes")
        return

    st.success(f"✅ Found **{result.total_offers} flights** across **{result.countries_searched} countries**!")
    df: pd.DataFrame = pd.DataFrame(result.offers)

    st.divider()
    render_kpi_cards(result)
    st.divider()
    filtered_df: pd.DataFrame = render_filters(df)
    st.divider()
    render_results_table(filtered_df)
    st.divider()
    render_charts(df)
    st.divider()
    render_export_buttons(df, search_params)
    st.divider()
    st.markdown("<div style='text-align:center; color:gray; font-size:0.8em; padding: 20px 0;'>Prices shown are indicative and converted to EUR for comparison only. Actual booking prices may vary. Always verify on the airline's website.</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
