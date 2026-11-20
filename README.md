# MediCart

Online medicine and healthcare shopping platform with AI-assisted prescription reading.
Final-year engineering project built with React, FastAPI and PostgreSQL (Neon).

MediCart is a demonstration system. It is **not a licensed pharmacy** and processes **no real payments**.
The catalogue comes from public datasets (see section 8); stock levels, discounts, the prescription
flag and the demo accounts are generated for demonstration.

**To install and run it, follow [SETUP_GUIDE.md](SETUP_GUIDE.md).**

---

## 1. Problem statement

Buying medicines online usually means typing every item from a paper prescription by hand, and
prescription-only medicines still need a pharmacist to look at the document before anything ships.
MediCart lets a customer upload a photo or PDF of a prescription, reads it with OCR and a language
model, shows the extracted medicines next to the catalogue matches, lets the customer correct them,
and routes prescription-only items to a pharmacist for approval before the order is fulfilled.

## 2. Objectives

- A shopping experience similar to a mainstream e-commerce site: catalogue, search, cart, addresses,
  checkout, order tracking.
- A prescription pipeline that is honest about uncertainty: OCR confidence, fuzzy match levels,
  flagged fields, mandatory customer confirmation and pharmacist verification.
- Strict role separation (customer / pharmacist / admin) enforced on the server.
- Zero-budget stack: free tiers and open-source libraries only.

## 3. Features

**Customer**
- Register and sign in with mobile number and password (Argon2 hashing, JWT access + refresh tokens).
- Home page with categories, deals, featured and popular products, recently viewed, offer ticker.
- Catalogue with search (name, brand, generic, strength, formulation), filters (category, price,
  stock, prescription), sorting and pagination.
- Product page with pack-size variants, discounts and prescription badges.
- Persistent server-side cart (survives logout), quantity limits, live stock checks.
- Multiple saved addresses with a default, used at checkout.
- Checkout with cash on delivery or a simulated online payment; delivery is free above ₹499,
  otherwise ₹40.
- Order history with In progress / Delivered / Cancelled tabs and delivery dates, order detail with
  timeline, cancellation with automatic restock/refund.
- Prescription upload (JPG, PNG, PDF; drag-and-drop; 10 MB limit) with a review screen where every
  field can be edited, matches can be chosen from candidates or searched, and items can be excluded
  or added manually. "Confirm and add to cart" puts one pack of each matched medicine in the cart.

**Pharmacist**
- Review is optional by default: the customer ticks "Ask a pharmacist to review" and the linked order
  waits until the pharmacist decides. With `REQUIRE_PHARMACIST_APPROVAL=true` every prescription with
  prescription-only medicines must be approved before those medicines can be added or dispatched.
- Verification queue of the prescriptions that need a decision.
- Detail view with OCR text, structured items, customer edits, uncertainty flags and linked orders.
- Approve / reject / request clarification with notes; history of all decisions.
- Approval moves waiting orders forward; rejection cancels them and restocks.

**Admin**
- Dashboard: customers, medicines, orders by status, simulated revenue, prescription statistics,
  low stock.
- Medicines, pack sizes, prices and inventory; categories; customer and staff management
  (role changes, deactivation); order status updates, including a one-click "Mark delivered" (there
  is no courier, so the admin can move an order forward to any later stage); prescription
  monitoring; audit log.

**Prescription pipeline**
- OpenCV preprocessing: resize, grayscale, bilateral denoise, CLAHE contrast, projection-profile
  deskew, unsharp mask, adaptive threshold.
- OCR: RapidOCR (PaddleOCR models on ONNX Runtime, pip-only) by default; Tesseract if installed;
  experimental TrOCR for handwriting as an optional extra.
- Groq LLM (OpenAI-compatible SDK) turns OCR text into strict JSON; every name is checked against
  the OCR text so the model cannot invent medicines or strengths. If Groq is unavailable the
  rule-based parser takes over and the result is marked as such.
- Catalogue matching with exact / possible / uncertain / none levels; fuzzy matches are never
  auto-selected.
- Original images are processed in memory and never stored; only extracted text and structured
  items are kept.

## 4. Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, React Router, TanStack Query, Axios, Lucide |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL (Neon in production, Docker locally), SQLite for unit tests |
| Vision / OCR | OpenCV (headless), RapidOCR (ONNX Runtime), pytesseract (optional), TrOCR (optional) |
| PDF | pypdfium2 |
| LLM | Groq API through the `openai` Python SDK |
| Auth | Argon2 (argon2-cffi), PyJWT, role-based dependencies |
| Tooling | uv, ruff, pytest, ESLint, TypeScript |
| Deployment | One Vercel project: FastAPI function + Vite bundle served from the CDN |

## 5. Architecture

```
Browser (React SPA)
   │  /api/*  (JSON, Bearer token)
   ▼
FastAPI (backend/app)
   ├── routers/      thin HTTP layer, role checks
   ├── services/     business logic, transactions
   ├── computer_vision/  OpenCV preprocessing, OCR engines, PDF rendering
   ├── ai/           Groq client, prompt, structured-output validation, rule-based fallback
   └── models/       SQLAlchemy models (16 tables) + Alembic migrations
   ▼
PostgreSQL (Neon)
```

Locally the Vite dev server proxies `/api` to uvicorn. In production FastAPI serves the built
bundle (`app.frontend`) and Vercel promotes it to the CDN, so the site and the API share one domain.

### Prescription flow

1. `POST /api/prescriptions/analyse` receives the file, validates magic bytes and size, renders PDF
   pages, preprocesses each page and runs OCR.
2. A heuristic (stroke-height variance + OCR confidence) or the customer's hint decides printed vs
   handwritten. Handwritten documents trigger the disclaimer and, if enabled, TrOCR.
3. OCR text goes to Groq (or the rule-based parser). The output is validated with Pydantic and
   guarded against invented names/strengths.
4. Each medicine is matched against the catalogue. Exact single matches are pre-selected; everything
   else is offered as candidates.
5. The response includes session-only preview images. The prescription record stores text and
   items, not the file.
6. `POST /api/prescriptions/confirm` records the customer's corrections and adds one pack of each
   matched, in-stock medicine to the cart (`add_to_cart: false` skips this). The response lists what
   was added and what was skipped and why. If the customer asked for a review (or approval is
   mandatory), the prescription goes to the pharmacist queue.
7. Orders containing prescription-only items are linked to a confirmed prescription that covers them
   (the newest one is picked automatically). They go straight to fulfilment unless a review is open,
   in which case they wait in `verification_pending` until the pharmacist decides.

## 6. Database design

Tables: `users`, `addresses`, `medicine_categories`, `medicines`, `products`, `inventory`, `carts`,
`cart_items`, `prescriptions`, `prescription_items`, `pharmacist_verifications`, `orders`,
`order_items`, `payments`, `shipments`, `audit_logs`.

Key points:
- Monetary values use `NUMERIC(10,2)`; order items store price snapshots.
- `orders.address_snapshot` keeps the delivery address as JSON so later edits do not rewrite history.
- `orders.prescription_id` links an order to the prescription that authorises its Rx items.
- `prescriptions.extracted_text` is capped and no image bytes are ever stored.
- Foreign keys cascade where the child has no meaning without the parent (cart items, order items)
  and set NULL where history must survive (audit actor, order product).
- Order status transitions are enforced in `app/models/enums.py` (`ORDER_TRANSITIONS`).

Models live in `backend/app/models/`; the initial migration is
`backend/migrations/versions/7fc4c3fc9427_initial_schema.py`.

## 7. Folder structure

```
medicart/
├── api/index.py              Vercel entrypoint (adds backend/ to sys.path, exposes `app`)
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app factory
│   │   ├── core/             settings, security, dependencies, errors, rate limiting
│   │   ├── database/         engine + session
│   │   ├── models/           SQLAlchemy models and enums
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── routers/          auth, catalogue, cart, addresses, orders, prescriptions, pharmacist, admin
│   │   ├── services/         business logic
│   │   ├── computer_vision/  documents.py, preprocessing.py, ocr/ (rapidocr, tesseract, trocr)
│   │   ├── ai/               groq_client.py, prompts.py, schemas.py, structuring.py
│   │   └── utils/            text normalisation, validators, pagination
│   ├── migrations/           Alembic
│   ├── scripts/              seed.py, seed_data.py
│   ├── tests/                pytest suite
│   ├── .env.example
│   ├── requirements.txt      pinned, exported from uv.lock
│   └── alembic.ini
├── frontend/
│   ├── public/samples/       fictional sample prescriptions for demos
│   └── src/
│       ├── components/       UI primitives, address form, medicine picker
│       ├── context/          auth, toasts
│       ├── hooks/            cart, utilities
│       ├── layouts/          AuthLayout, CustomerLayout, StaffLayout
│       ├── pages/            auth/, customer/, pharmacist/, admin/
│       ├── services/         axios client + API modules
│       ├── types/            shared TypeScript types
│       └── utils/
├── pyproject.toml            Python deps + Vercel entrypoint/build config
├── uv.lock
├── vercel.json
└── README.md
```

## 8. Local setup

### Prerequisites

- Python 3.12 (`py -3.12 --version` on Windows, `python3.12 --version` elsewhere)
- Node.js 20+ and npm
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A PostgreSQL database: a free Neon project, or Docker for a local instance

Install Python from https://www.python.org/downloads/ and Node.js from https://nodejs.org/.
Install uv with `pip install uv` or the installer on its site.

### Database

**Neon:** create a project at https://neon.tech, open *Connection details*, choose the **pooled**
connection string and copy it (it ends with `?sslmode=require`).

**Local Docker alternative:**

```bash
docker run -d --name medicart-pg -e POSTGRES_USER=medicart -e POSTGRES_PASSWORD=medicart -e POSTGRES_DB=medicart -p 5433:5432 postgres:16-alpine
```

### Backend

```bash
# from the repository root
uv venv --python 3.12 .venv
uv sync --extra dev
```

Or with pip:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r backend/requirements.txt
```

Create `backend/.env` from `backend/.env.example` and fill in:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require   # Neon pooled URL
JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
GROQ_API_KEY=<your key>
GROQ_MODEL=<a model enabled on your Groq account, e.g. llama-3.3-70b-versatile>
```

Run migrations and seed demo data:

```bash
cd backend
python -m alembic upgrade head
python -m scripts.seed
```

Start the API:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/api/docs
- Health check: http://localhost:8000/api/health (database, OCR engine and Groq status)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to port 8000; if the API runs elsewhere,
copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_PROXY`.

### Demo accounts (created by the seed script)

| Role | Mobile | Password |
| --- | --- | --- |
| Admin | 9000000001 | Admin@1234 |
| Pharmacist | 9000000002 | Pharma@1234 |
| Customer | 9000000003 | Customer@1234 |

Change these before any public deployment (or run the seed only against a demo database).

### OCR engines

- **RapidOCR** is installed with the base dependencies and used automatically. First use downloads
  nothing (models ship in the wheel) but takes a few seconds to initialise.
- **Tesseract** is used when `OCR_ENGINE=tesseract` or when RapidOCR is missing. Install the binary
  (Windows: https://github.com/UB-Mannheim/tesseract/wiki) and set `TESSERACT_CMD` if it is not on
  `PATH`.
- **Groq vision (recommended for handwriting):** printed-text OCR engines cannot read doctor
  handwriting. Set `GROQ_VISION_MODEL` to an image-capable model on your Groq account
  (`qwen/qwen3.8-27b` worked in our tests; the llama-4 models also accept images where available)
  and handwritten pages, or pages where OCR found no text, are transcribed by the model instead.
  The transcript goes through the same structuring, invention guard and catalogue matching as OCR
  text, and the review page says which path was used. The same model can serve as `GROQ_MODEL`.
- **TrOCR (handwriting, experimental, local only):**

  ```bash
  uv sync --extra handwriting      # installs torch + transformers (large download)
  ```

  then set `ENABLE_HANDWRITING_OCR=true`. The model (`microsoft/trocr-base-handwritten`, ~1.3 GB)
  downloads on first use. It reads one text line at a time using the OCR detection boxes and works
  on neat English handwriting; expect weak results on typical clinical handwriting. It is too large
  for the Vercel function and is meant for local runs.

Sample fictional prescriptions for testing are in `frontend/public/samples/` and can be loaded from
the upload page.

### Loading the real medicine catalogue (Kaggle)

The seed script only adds a small sample. For a realistic catalogue, import the public Kaggle
datasets *A-Z Medicine Dataset of India* (products, prices, packs, manufacturers, salts) and
*250K Medicines Usage, Side Effects and Substitutes* (uses, side effects, therapeutic class):

```bash
uv sync --extra dev --extra data            # adds kagglehub
```

```bash
python -c "import kagglehub; print(kagglehub.dataset_download('shudhanshusingh/az-medicine-dataset-of-india')); print(kagglehub.dataset_download('shudhanshusingh/250k-medicines-usage-side-effects-and-substitutes'))"
```

```bash
cd backend
python -m scripts.import_catalogue --az <path>/A_Z_medicines_dataset_of_India.csv --usage <path>/medicine_dataset.csv --reset
```

About 246,000 non-discontinued products load in roughly 10-15 minutes (`--limit 20000` for a
quick run). Prices are taken as MRP; stock levels and small demo discounts are generated; the
prescription flag is a heuristic from the therapeutic class and salt names, not a legal schedule.
Matching uses PostgreSQL trigram indexes (`pg_trgm`), so it stays fast at this size. Neon's free
tier holds this catalogue comfortably.

### Adding general health products (ORS, health drinks, personal care, first aid)

The medicine datasets only contain prescription-style allopathic products. Everyday health items
come from two more public datasets plus a short curated list:

| Source | What is used |
| --- | --- |
| Kaggle `surajjha101/bigbasket-entire-product-list-28k-datapoints` | Beauty & Hygiene (skin, hair, bath, oral, feminine care, health & medicine, Ayurveda, supplements, masks, antiseptics, bandages), Baby Care, health drinks. Groceries and household goods are skipped. |
| Hugging Face `SageLiao/Amazon-product-healthcare` | Health-relevant rows only: thermometers, BP monitors, nebulizers, glucose strips, health drinks, supplements, personal care. Cleaners and appliances are skipped. No licence is stated on the dataset card. |
| Built-in list in `scripts/import_health_products.py` | ORS powders (Electral, Dr Morepen, Prolyte, Electrorush, WHO formula) and ready-to-drink electrolyte drinks (ORSL, Enerzal, Prolyte, Electrorush). No open dataset lists them, so the names are real brands and the prices are approximate demo values. |

```bash
python -c "import kagglehub; print(kagglehub.dataset_download('surajjha101/bigbasket-entire-product-list-28k-datapoints'))"
```

```bash
python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('SageLiao/Amazon-product-healthcare', 'Modified_Final_Dataset.csv', repo_type='dataset'))"
```

```bash
cd backend
python -m scripts.import_health_products --bigbasket "<path>/BigBasket Products.csv" --amazon <path>/Modified_Final_Dataset.csv
```

The import only adds rows (keyed by SKU, safe to re-run) and marks nothing as prescription-only.
ORS powders carry the WHO salt composition, so "ORS" written on a prescription matches them;
electrolyte drinks are described as not a substitute for ORS during diarrhoea. Catalogue search
drops trailing words when a multi-word query finds nothing, so "ORS juice" still lists ORS products.

## 9. Running the tests

```bash
cd backend
python -m pytest            # 60 tests, SQLite in-memory, ~30 s
python -m ruff check app    # lint
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

The suite covers registration/login/roles, catalogue search and filters, cart persistence and stock
limits, order placement/cancellation/status transitions, upload validation, the OCR+matching
pipeline with a fake engine, Groq fallback and invention guard, confirmation, pharmacist gating,
and the RapidOCR engine on a synthetic image (`-m slow`).

## 10. API overview

All endpoints are under `/api`. Interactive documentation: `/api/docs`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET/PUT /auth/me`, `POST /auth/change-password`, `POST /auth/logout` |
| Catalogue | `GET /categories`, `GET /home`, `GET /medicines`, `GET /medicines/search`, `GET /medicines/{id}`, `GET /products/{id}` |
| Cart | `GET /cart`, `POST /cart/items`, `PUT /cart/items/{id}`, `DELETE /cart/items/{id}`, `DELETE /cart` |
| Addresses | `GET/POST /addresses`, `PUT/DELETE /addresses/{id}`, `POST /addresses/{id}/default` |
| Orders | `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/cancel` |
| Prescriptions | `POST /prescriptions/analyse`, `POST /prescriptions/confirm`, `GET /prescriptions`, `GET /prescriptions/{id}`, `GET /prescriptions/{id}/status`, `POST /prescriptions/{id}/request-review` |
| Pharmacist | `GET /pharmacist/verification-requests`, `GET /pharmacist/verification-requests/{id}`, `POST /pharmacist/verification`, `GET /pharmacist/history`, `GET /pharmacist/summary` |
| Admin | `GET /admin/dashboard`, `GET/PATCH /admin/users`, `/admin/categories`, `/admin/medicines`, `/admin/products`, `/admin/orders`, `/admin/prescriptions`, `GET /admin/audit-logs` |
| Health | `GET /health` |

Errors use one envelope: `{"error": {"code": "...", "message": "...", "details": ...}}`.
Validation errors return the offending fields in `details`.

## 11. Deployment (Vercel)

The repository is configured for a single Vercel project.

1. Push the repository to GitHub and import it in Vercel (framework preset: FastAPI is detected
   from `pyproject.toml`; the root directory is the repository root).
2. `pyproject.toml` sets `tool.vercel.entrypoint = "api.index:app"` and a build script that runs
   `npm ci && npm run build` in `frontend/`. FastAPI serves `frontend/dist` with an SPA fallback and
   Vercel promotes it to the CDN.
3. Add environment variables in the Vercel dashboard: `DATABASE_URL` (Neon pooled URL),
   `JWT_SECRET`, `GROQ_API_KEY`, `GROQ_MODEL`, `APP_ENV=production`,
   `FRONTEND_URL=https://<your-project>.vercel.app`. With `APP_ENV=production` the app refuses to
   start with a placeholder secret or a non-PostgreSQL database.
4. Run the migration and seed against Neon from your machine
   (`DATABASE_URL=... python -m alembic upgrade head`), or add them to the build script.
5. `vercel.json` raises the function timeout to 60 s and excludes tests, sources and virtualenvs
   from the bundle. The Python bundle (FastAPI + OpenCV headless + ONNX Runtime + RapidOCR models)
   is well under Vercel's 500 MB limit.
6. After deploying, check `https://<project>.vercel.app/api/health`: `database` should be `ok` and
   `ocr.selected` should be `rapidocr`.

The deployment configuration follows Vercel's current FastAPI documentation but has not been
deployed from this repository yet; treat the first deployment as a test and verify the health
endpoint, login, catalogue and an upload.

## 12. Known limitations

- Handwritten recognition is experimental. Without the optional TrOCR extra, handwritten documents
  are read with the printed-text engine and clearly marked as unreliable.
- Groq output quality depends on the configured model; without a key the rule-based parser is used
  and every field is flagged for review.
- Rate limiting is in-process. On serverless platforms each instance keeps its own counters.
- JWTs are stateless; logout clears tokens on the client and writes an audit entry, but an access
  token stays valid until it expires (30 minutes by default).
- Payments are simulated. No card details are collected.
- Password reset is intentionally absent because there is no verified channel (email/SMS) to deliver
  a reset link safely.
- Product images are not hosted; cards use category placeholders unless an `image_url` is set.
- Prescription images are processed by a third-party AI service (Groq). Use only synthetic or
  consented documents in demonstrations.
#   m e d i c a r t  
 