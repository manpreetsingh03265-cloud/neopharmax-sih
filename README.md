# Neopharmax Full-Stack SIH Prototype

A complete, runnable Flask + SQLite prototype for the Neopharmax patient-data collection platform.

## Features
- Responsive healthcare dashboard
- Login/logout
- SQLite patient database
- Create, view, search, update and delete patient records
- AI-assisted educational suggestion endpoint
- Analytics/statistics API
- CSV patient export
- Local browser-friendly UI
- No external database or API key required for the demo

## Demo login
Email: `demo@neopharmax.local`
Password: `demo123`

## Run on Windows/macOS/Linux

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Start: `python app.py`
6. Open: `http://127.0.0.1:5000`

The database file `neopharmax.db` is created automatically on first launch.

## Important for SIH
This is a demonstration/prototype system. Do not enter real patient-identifiable or clinical data. For a production deployment, add proper authentication, HTTPS, audit logs, access controls, encryption, backups, consent/privacy controls, validated clinical rules/models, and an approved healthcare database/API.
