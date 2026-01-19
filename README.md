# Alma Assignment

Extracts data from passport + G-28 PDFs using Gemini 3 Flash, then auto-fills any web form using Browserbase.

## [Updated] Loom Recording URL: https://www.loom.com/share/3fa169c38a894a2c9a94991a21198447

## Local Setup

### 1. Clone Repository

```bash
git clone <repo>
cd <repo>
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

**Save the `.env` file provided via email** to the project root directory.

Make sure the `.env` file is in the same directory as `main.py`:

```
.
├── main.py
├── form_populator.py
├── models.py
├── .env          ← Save the file here
└── requirements.txt
```

The `.env` file contains your API keys:

```env
GOOGLE_AI_API_KEY=...
BROWSERBASE_API_KEY=...
BROWSERBASE_PROJECT_ID=...
```

### 4. Run the Application

```bash
python3 main.py
```

The app will start the Gradio APP UI at **http://localhost:8000**.
