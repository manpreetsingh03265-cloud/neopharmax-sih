# NeoPharmX Full-Stack SIH Prototype

NeoPharmX is a Flask + SQLite demonstration of a two-sided patient case-taking workflow for SIH26047.

## Prototype workflow

**Patient:** Register/demo login → NeoPharmX Patient ID → appointment → voice/text case-taking → reports/prescriptions → review → submit.

**NeoPharmX:** Structure information → maintain patient record → rule-based educational assistance → drug information.

**Healthcare professional:** Patient queue → search Patient ID → review structured history/documents → AI-assisted information → final professional decision.

## Demo accounts

### Healthcare professional
- Email: `demo@neopharmax.local`
- Password: `demo123`

### Patient
- Email: `patient@neopharmax.local`
- Password: `patient123`
- Patient ID: `NPX-000001`

## Current features

- Role-based demo login for patient and healthcare professional
- NeoPharmX Patient IDs (`NPX-XXXXXX`)
- Patient profile and structured case-taking
- Patient ↔ physician connection-code workflow
- Appointment request and queue
- Voice case-taking using browser speech recognition when supported
- English/Hindi/regional-language UI fields and language selection
- Medical report/prescription upload for PDF/JPG/PNG demo files
- Physician patient records and search
- Rule-based educational AI assistance
- Drug information demo module
- Allergy and medication fields
- CSV export for demonstration
- Responsive dashboard

## Roadmap shown in the prototype

- OCR extraction from uploaded reports and prescriptions
- ABHA/ABDM consent-based onboarding and record linkage
- FHIR/HIS/EMR interoperability
- Clinical validation of decision-support rules/models
- Strong production authentication, encryption, audit logs and access controls
- Multilingual conversational case-taking and validated clinical alerts

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Start: `python app.py`
6. Open: `http://127.0.0.1:5000`

The SQLite database is created automatically on first launch.

## Safety

This is a demonstration/prototype system. Use synthetic/demo data only. The AI module is rule-based educational decision support and does not independently diagnose or prescribe. Production deployment would require appropriate clinical validation, privacy/consent controls, secure infrastructure, auditability and applicable healthcare regulations.
