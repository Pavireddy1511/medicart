# MediCart: setup and run guide

This guide takes you from the unzipped folder to a running MediCart on your own machine.
The package is already connected to a cloud database (Neon) that holds about 250,000 products and the
demo accounts, and to Groq for prescription reading. You only install the dependencies and start
two servers.

---

## 1. Login credentials

These accounts already exist in the configured database.

| Role | Mobile number | Password | Opens on |
| --- | --- | --- | --- |
| **Admin** | **9000000001** | **Admin@1234** | Admin dashboard (`/admin`) |
| Pharmacist | 9000000002 | Pharma@1234 | Pharmacist desk (`/pharmacist`) |
| Customer | 9000000003 | Customer@1234 | Shop (`/`) |

New customers can register from the sign-up page. Pharmacist and admin accounts can only be
created by promoting a user in **Admin → Customers & staff**.

---

## 2. What is in the package

```
MediCart/
├── SETUP_GUIDE.md          this guide
├── README.md               project report: architecture, API, database, limitations
├── backend/
│   ├── .env                live configuration: Neon database URL, Groq key, models  (keep private)
│   ├── .env.example        the same settings with placeholders
│   ├── app/                FastAPI application
│   ├── migrations/         Alembic database migrations
│   ├── scripts/            seed and dataset import scripts
│   ├── tests/              pytest suite
│   └── requirements.txt    Python dependencies
├── frontend/               React + TypeScript + Vite app
├── api/index.py            Vercel entry point
├── datasets/               the public datasets the catalogue was built from (only needed to rebuild it)
├── pyproject.toml, uv.lock, vercel.json
```

`node_modules` and the Python virtual environment are not included. Step 3 recreates them.

### What `backend/.env` configures

| Setting | Value in this package | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | Neon PostgreSQL (pooled, SSL) | Cloud database with all data already loaded |
| `GROQ_API_KEY` | your Groq key | Used only by the backend |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Turns OCR text into structured medicines |
| `GROQ_VISION_MODEL` | `qwen/qwen3.8-27b` | Reads handwritten or unclear prescription pages |
| `JWT_SECRET` | development value | Signs login tokens. Replace it before any public deployment |
| `APP_ENV` | `development` | |
| `OCR_ENGINE` | `auto` | RapidOCR (installed with the requirements) |

Optional settings you can add to `backend/.env`:

| Setting | Default | Effect |
| --- | --- | --- |
| `REQUIRE_PHARMACIST_APPROVAL` | `false` | `true` makes pharmacist approval mandatory before prescription-only medicines can be added to the cart or delivered |
| `ENABLE_HANDWRITING_OCR` | `false` | `true` enables the local TrOCR model (see section 8) |

---

## 3. Prerequisites (install once)

| Software | Version | Check with | Download |
| --- | --- | --- | --- |
| Python | **3.12.x** (3.11 and 3.13 are not supported) | `py -3.12 --version` (Windows) or `python3.12 --version` | https://www.python.org/downloads/ |
| Node.js | 20 or newer (LTS) | `node --version` | https://nodejs.org/ |
| Internet | needed | | The database and Groq are cloud services |

On Windows, tick **"Add python.exe to PATH"** in the Python installer. Allow about 2 GB of disk
space for the dependencies.

---

## 4. Install (once)

The commands below assume the package was unzipped to `D:\MediCart`. Use your own path.

### Backend (Windows PowerShell)

```powershell
cd D:\MediCart
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

If PowerShell refuses to run `Activate.ps1`, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Command Prompt users activate with `.venv\Scripts\activate.bat` instead.

### Backend (macOS / Linux)

```bash
cd ~/MediCart
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

### Confirm the database is reachable

With the virtual environment active:

```bash
cd backend
python -m alembic upgrade head
```

It should finish without errors. Nothing changes, because the Neon database is already up to date.
The first connection can take up to 15 seconds while Neon wakes the database.

---

## 5. Run (every time)

Use two terminals.

### Terminal 1: backend API

```powershell
cd D:\MediCart
.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --port 8000
```

(macOS / Linux: `source .venv/bin/activate` instead of the second line.)

Wait for `Application startup complete`, then check:

- Health: http://localhost:8000/api/health should show `"database": "ok"` and `"groq_configured": true`
- API documentation (Swagger): http://localhost:8000/api/docs

### Terminal 2: frontend

```bash
cd D:\MediCart\frontend
npm run dev
```

Open **http://localhost:5173** and sign in with one of the accounts in section 1.

If port 5173 is taken, run `npm run dev -- --port 5174` and open http://localhost:5174.
The frontend forwards all `/api` calls to the backend on port 8000.

### Alternative: one server only

Build the frontend once and let FastAPI serve it:

```bash
cd frontend
npm run build
cd ../backend
python -m uvicorn app.main:app --port 8000
```

Then open **http://localhost:8000**. Rebuild the frontend after changing frontend code.

To stop a server, press `Ctrl+C` in its terminal. After changing backend code, stop and start the
backend again.

---

## 6. A five-minute demo

1. **Customer (9000000003).** Browse categories in the sidebar, search "ORS" or "Dolo", open a product and add it to the cart.
2. **Prescription.** Click **Upload prescription**, use the "printed prescription" sample link under the drop zone, tick the consent box and click **Analyse**. On the review screen, tap the right product where a line asks, then **Confirm and add to cart**. The matched medicines go straight into the cart.
3. **Checkout.** Pick or add an address, choose Cash on delivery and place the order. Tick "Ask a pharmacist to review" on the review screen if you want the order to wait for the pharmacist.
4. **Admin (9000000001).** Open **Orders** and click **Mark delivered** on the order, or open it and move it through the stages. The dashboard shows totals, low stock and prescription statistics.
5. **Customer again.** **My orders → Delivered** shows the order with its delivery date.
6. **Pharmacist (9000000002).** Reviews prescriptions that customers sent for review: approve, reject or ask for clarification.

---

## 7. Starting from an empty database (optional)

Only needed if you point `DATABASE_URL` at a new Neon project or a local PostgreSQL. The datasets
are in the `datasets/` folder of this package.

**Local PostgreSQL with Docker:**

```bash
docker run -d --name medicart-pg -e POSTGRES_USER=medicart -e POSTGRES_PASSWORD=medicart -e POSTGRES_DB=medicart -p 5433:5432 postgres:16-alpine
```

Then set `DATABASE_URL=postgresql://medicart:medicart@localhost:5433/medicart` in `backend/.env`.

**Build the database** (from `backend/`, virtual environment active, in this order):

```bash
python -m alembic upgrade head
```

```bash
python -m scripts.seed
```

```bash
python -m scripts.import_catalogue --az "../datasets/A_Z_medicines_dataset_of_India.csv" --usage "../datasets/medicine_dataset.csv" --reset
```

```bash
python -m scripts.import_health_products --bigbasket "../datasets/BigBasket Products.csv" --amazon "../datasets/Modified_Final_Dataset.csv"
```

| Step | What it does | Time |
| --- | --- | --- |
| `alembic upgrade head` | Creates the 16 tables and search indexes | seconds |
| `scripts.seed` | Categories, the three demo accounts, a small sample catalogue | seconds |
| `scripts.import_catalogue` | About 242,000 medicines. `--reset` replaces the sample catalogue | 3 min local, about 30 min to Neon |
| `scripts.import_health_products` | About 7,900 health, personal-care and first-aid products plus ORS | 1 min local, about 15 min to Neon |

Add `--limit 20000` to `import_catalogue` for a quick, smaller catalogue.

| Dataset file | Source |
| --- | --- |
| `A_Z_medicines_dataset_of_India.csv` | Kaggle: shudhanshusingh/az-medicine-dataset-of-india |
| `medicine_dataset.csv` | Kaggle: shudhanshusingh/250k-medicines-usage-side-effects-and-substitutes |
| `BigBasket Products.csv` | Kaggle: surajjha101/bigbasket-entire-product-list-28k-datapoints |
| `Modified_Final_Dataset.csv` | Hugging Face: SageLiao/Amazon-product-healthcare |

---

## 8. Optional extras

**Run the tests** (uses an in-memory database, not Neon):

```bash
pip install pytest ruff
cd backend
python -m pytest
```

All 80 tests should pass. In `frontend/`, `npm run lint` and `npm run build` check the frontend.

**Local handwriting model (TrOCR).** Not needed when `GROQ_VISION_MODEL` is set. It downloads
about 1.3 GB the first time it runs:

```bash
pip install torch transformers pillow
```

Then set `ENABLE_HANDWRITING_OCR=true` in `backend/.env` and restart the backend.

**Deploying to Vercel.** See section 11 of `README.md`. Copy the values from `backend/.env` into
the Vercel project's environment variables, set `APP_ENV=production` and a new random `JWT_SECRET`.

---

## 9. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `py` or `python3.12` not found | Install Python 3.12 and reopen the terminal |
| `pip install` fails on a package | Make sure the virtual environment uses Python 3.12: `python --version` |
| First request is slow or times out once | Neon pauses idle databases; the first connection wakes it in 5 to 15 seconds. Refresh |
| Health shows `"database": "error"` | Check the internet connection and `DATABASE_URL` in `backend/.env` |
| Port 8000 already in use | Start the backend with `--port 8001`, create `frontend/.env.local` containing `VITE_API_PROXY=http://127.0.0.1:8001`, restart `npm run dev` |
| Port 5173 already in use | `npm run dev -- --port 5174` |
| Pages load but every action says "sign in" | You switched databases; sign out and sign in again |
| Prescription upload takes 10 to 20 seconds | Normal on the first upload: the OCR models load, then Groq reads the page |
| Notes say Groq is unavailable | Groq key invalid or rate-limited. The app falls back to simple rules; check `GROQ_API_KEY` |

---

## 10. Keep the credentials safe

`backend/.env` in this package contains a live database password and a live Groq API key.

- Do not upload the package or `backend/.env` to GitHub or share it publicly. `.gitignore` already excludes `.env`.
- If it was shared, rotate both: Neon console → your project → **Roles** → reset the password;
  Groq console → **API Keys** → revoke and create a new key. Then update `backend/.env`.
- Change the demo account passwords before showing the site to anyone outside your team.
