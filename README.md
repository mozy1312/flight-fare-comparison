# Flight Fare Comparison

> A production-ready Streamlit web application that compares flight fares across multiple Point-of-Sale (POS) countries to find the cheapest tickets.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30+-ff4b4b.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

- **Multi-POS Price Comparison** — Search across 15 countries simultaneously to find price differences
- **Real-time Flight Search** — Powered by the Amadeus Flight Offers Search API
- **Currency Normalization** — All prices converted to EUR for fair comparison
- **Interactive Dashboard** — KPI cards, filters, sortable data table, and 4 Plotly charts
- **Data Export** — Download results as CSV or Excel with one click
- **Dark Mode Compatible** — Beautiful UI in both light and dark themes
- **Responsive Design** — Works on desktop, tablet, and mobile
- **Input Validation** — IATA code validation, date checks, and helpful error messages
- **Progress Tracking** — Visual progress bar during multi-country searches

## Prerequisites

- **Python 3.12+**
- **Git**
- **Amadeus API key** (free tier — see [Getting an API Key](#getting-an-amadeus-api-key))

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/mozy1312/flight-fare-comparison.git
cd flight-fare-comparison
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Amadeus API credentials:

```env
AMADEUS_API_KEY=your_api_key_here
AMADEUS_API_SECRET=your_api_secret_here
```

### 5. Run the application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## Getting an Amadeus API Key

Follow these steps to get your free Amadeus API credentials:

1. Go to [developers.amadeus.com/register](https://developers.amadeus.com/register)
2. Create a free account or log in
3. Navigate to your **Account** → **My Apps**
4. Click **Create new app**
5. Give your app a name (e.g., "Flight Fare Finder")
6. Copy the **API Key** and **API Secret** into your `.env` file
7. You're ready to search!

> The free tier includes 2,000 API calls/month, which is plenty for personal use.

---

## Deploying to Streamlit Cloud

Deploy the app for free in minutes:

1. Push your code to a public GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with GitHub
4. Click **New app**
5. Select your repository, branch (`main`), and file (`app.py`)
6. Add your Amadeus credentials in **Settings** → **Secrets**:
   ```toml
   AMADEUS_API_KEY = "your_api_key_here"
   AMADEUS_API_SECRET = "your_api_secret_here"
   ```
7. Click **Deploy**

Your app will be live at `https://<your-app>.streamlit.app`.

---

## Project Structure

```
flight-fare-comparison/
├── app.py                    # Main Streamlit application entry point
├── config.py                 # Central configuration & environment
├── proxy_manager.py          # Country/POS proxy definitions
├── api_client.py             # Amadeus API client
├── search_engine.py          # Core search orchestration
├── currency.py               # Currency conversion utilities
├── utils.py                  # Shared helpers
├── models.py                 # Pydantic data models
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
├── README.md                 # This file
├── .gitignore
├── assets/
│   └── style.css             # Custom Streamlit CSS overrides
└── pages/
    └── about.py              # About page (auto-routed by Streamlit)
```

## Configuration

All configuration is managed through environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `AMADEUS_API_KEY` | Yes | Your Amadeus API key |
| `AMADEUS_API_SECRET` | Yes | Your Amadeus API secret |
| `TRAVELPAYOUTS_TOKEN` | No | Travelpayouts API token for price trends |
| `AVIATIONSTACK_API_KEY` | No | Aviationstack key for flight tracking |
| `DEBUG` | No | Set to `true` for verbose debug logging |

## POS Comparison Strategy

Airlines frequently practice **price discrimination by market** — the same flight can have different prices depending on which country you appear to be booking from. This app exploits that by:

1. Querying the Amadeus API with each country's **local currency**
2. Converting all returned prices to **EUR** using real-time exchange rates
3. Presenting a unified comparison so you can book from the cheapest market

The 15 default countries span multiple continents and price tiers, giving you broad coverage.

## Troubleshooting

### "Invalid API credentials" error
- Double-check your `AMADEUS_API_KEY` and `AMADEUS_API_SECRET` in `.env`
- Ensure there are no extra spaces or quotes around the values
- Verify your Amadeus account is active at [developers.amadeus.com](https://developers.amadeus.com)

### "No flights found" message
- Try broadening your search (more countries, no direct-only filter)
- Check that your IATA airport codes are correct
- Try dates further in the future
- Verify the route is actually serviced by airlines

### "Rate limit exceeded" error
- The free Amadeus tier allows 2,000 calls/month
- Try reducing the number of countries in your search
- Wait a few minutes between searches

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Amadeus for Developers](https://developers.amadeus.com) — Flight data API
- [Streamlit](https://streamlit.io) — UI framework
- [Plotly](https://plotly.com) — Interactive charts
