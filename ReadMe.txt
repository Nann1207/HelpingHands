HelpingHands (TEAM NULL)
=====================

Volunteer matching platform for:
- Persons-in-Need (PIN)
- Corporate Volunteers (CV)
- CSR Representatives (CSR)
- Platform Admins (PA)

Built as a Django monolith with a Boundary–Control–Entity (BCE) structure, REST-style APIs and role-based Django templates.

-------------------------
1. TECHNOLOGY STACK
-------------------------
Backend: Django, Django REST Framework
Auth: Django Sessions (SimpleJWT optional)
Database: SQLite (default) or PostgreSQL
Utilities: Faker, CORS, python-dotenv, requests
Testing: pytest + pytest-django

Project Layout:
backend/
  config/      – Django settings + URLs
  core/        – Boundary / Control / Entity layers, model, tests
  frontend/    – Our frontend: HTML pages
  requirements.txt

---------------------------------------------
2. STEP BY STEP: RUNNING THE PROJECT
---------------------------------------------
This section is the full step-by-step guide to get HelpingHands running locally.

STEP 1 – Open a terminal
  - Windows: PowerShell or Command Prompt
  - macOS/Linux: Terminal

STEP 2 - Unzip the folder:
  - Extract it
  - Then in the terminal:
      cd path/to/HelpingHands/backend

STEP 3 – Create a virtual environment

Windows (PowerShell):
  python -m venv venv

macOS / Linux:
  python3 -m venv venv

STEP 4 – Activate the virtual environment

Windows (PowerShell):
  .\venv\Scripts\Activate.ps1

macOS / Linux:
  source venv/bin/activate

(You should see (venv) in front of your terminal prompt.)

STEP 5 – Install dependencies

  pip install --upgrade pip
  pip install -r requirements.txt

STEP 6 – (Optional but recommended) Create a .env file  
  See Section 3 for the example contents.

STEP 7 – Run Django checks

  python manage.py check

If there are no errors, continue.

STEP 8 – Apply database migrations

  python manage.py migrate

STEP 9 – (Optional) Seed demo data

  python manage.py seed_main_F1

STEP 10 – Start the development server

  python manage.py runserver

STEP 11 – Open the site in your browser

    http://localhost:8000/


STEP 12 – Run the test suite with pytest



Macbook:
First set up venv environment and run the following commands:
export DJANGO_SETTINGS_MODULE=config.settings
python -m pytest -q -s core/tests.py

---------------------------------------------
3. CONFIGURATION (OPTIONAL .env)
---------------------------------------------
Create a .env file in the backend/ folder with content similar to:

DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=you@example.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL="Helping Hands <you@example.com>"

SEA_LION_LLAMA_API_KEY=
SEA_LION_LLAMA_ENDPOINT=https://api.sea-lion.ai/v1/chat/completions
SEA_LION_LLAMA_MODEL=aisingapore/Gemma-SEA-LION-v4-27B-IT

Load environment (Unix example):
  set -a
  source .env

On Windows, you can also just rely on the values in config/settings.py or set env vars via System Settings / PowerShell.

---------------------------------------------
4. DATABASE & SEEDING
---------------------------------------------
Check Django setup:
  python manage.py check

Migrate database:
  python manage.py migrate

Flush demo data (optional):
  python manage.py flush --noinput

Seed demo data:
  python manage.py seed_main_F1

---------------------------------------------
5. RUNNING THE SERVER
---------------------------------------------
Start local dev server:
  python manage.py runserver

Visit:
  http://localhost:8000/


---------------------------------------------
6. RUNNING TESTS (pytest)
---------------------------------------------
Windows:
First set up venv environment and run the following commands:
$env:DJANGO_SETTINGS_MODULE='config.settings'
venv\Scripts\python -m pytest -q -s core\tests.py

Macbook:
First set up venv environment and run the following commands:
export DJANGO_SETTINGS_MODULE=config.settings
python -m pytest -q -s core/tests.py


---------------------------------------------
7. REQUIREMENTS
---------------------------------------------
Django
djangorestframework
djangorestframework-simplejwt
faker
pytest-django
psycopg2-binary
django-cors-headers
python-dotenv
requests

------------------
QUICK START 
------------------
cd HelpingHands/backend
python -m venv venv
.\venv\Scripts\Activate.ps1  (or: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_main_F1 (optional)
python manage.py runserver

Then open: http://localhost:8000/
---------------------------------------------
