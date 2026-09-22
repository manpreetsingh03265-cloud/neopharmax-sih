# NeoPharmX | SIH26003 Super Prototype

This version is structured around the supplied SIH26003 problem statement.

## Requirements covered
- Interactive cognitive games: Memory, Attention, Concentration, Daily Routine Recall, Pattern & Object Recognition
- Adaptive difficulty based on performance
- Multilingual-ready and voice-assisted interaction
- NER cultural-theme content slots
- Memory assistance reminders: medicines, hydration, daily activities, medical appointments
- Caregiver monitoring and alerts
- Health-worker review dashboard
- Low-connectivity/PWA cache and offline-first workflow
- Tablet/mobile responsive UI
- Longitudinal cognitive performance tracking
- Social/familiar memory prompts
- Accessibility controls
- SQLite persistence
- Flask backend
- Demo authentication

## Demo accounts
Elderly: elder@neopharmax.demo / demo123
Caregiver: caregiver@neopharmax.demo / demo123
Health Worker: healthworker@neopharmax.demo / demo123

## Run
pip install -r requirements.txt
python app.py
Open http://127.0.0.1:5000

## Render
Build: pip install -r requirements.txt
Start: gunicorn app:app

## Important boundary
The adaptive engine and cognitive scores are prototype demonstration logic, not clinically validated AI/ML or diagnostic measures. A production system requires clinical validation, consent, privacy/security controls, accessibility testing, validated multilingual/cultural content, robust offline synchronization, notifications and appropriate regulatory review.

## Separate role portals
- Elderly: My Care Portal, games, reminders, own activity history and personal memory prompts.
- Caregiver: Caregiver Portal, daily engagement, reminder adherence, trend alerts and caregiver notes.
- Health Worker: Health Worker Portal, longitudinal professional review, domain trends, routine adherence and follow-up workflow.
- All roles: My Profile with identity, age, role, language, voice and accessibility controls.
\n## Final role features\n- Separate role-selection login and dedicated login screens for Elderly Patient, Caregiver and Health Worker.\n- Live navigation-label language switching: English, Hindi, Assamese, Bengali, Manipuri and Khasi.\n- Patient can contact a health worker and see message history.\n- Caregiver and Health Worker portals show patient last-seen timestamp.\n