# SmartLabel Inspector

[![pipeline status](https://gitlab.com/vio4274337/smart-label-gov/badges/main/pipeline.svg)](https://gitlab.com/vio4274337/smart-label-gov/-/pipelines)

SmartLabel Inspector is a browser-based screening tool for packaged-product labels. It reads a label photo with local OCR, extracts the mandatory declarations, runs a small transparent rule set, and saves an evidence-led result that can be exported and shared.

It is a screening aid. It is not a legal certificate, a fine generator, or a replacement for a qualified decision-maker.

## Highlights

- **Four ways in**: front and back uploads, camera capture, pasted text, or two prepared demo samples that work without Tesseract.
- **Ten extracted fields**: MRP, net quantity, manufacturer or packer, date marking, best-before, batch, customer care phone and email, country of origin, FSSAI licence. Every value carries its confidence and the exact source text.
- **Nine deterministic checks**: MRP, net quantity, unit vs sold-by, unit sale price, manufacturer, date marking, customer care, origin for imports, FSSAI for food. Each returns pass, review, fail, or not applicable with a plain-language reason.
- **Evidence-led results**: status badge, metrics, check rows with icons, confidence bars, prepared OCR image, raw text.
- **Reports and sharing**: JSON, HTML, and PDF downloads plus WhatsApp and email share links with the summary prefilled.
- **Workspace**: Dashboard, New inspection, History with search and detail view, Rule sets with a live playground, Analytics, Project brief, Help, and functional Settings.
- **Local-first**: SQLite history, images processed in memory and discarded.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Tesseract must be installed and on PATH for real image OCR (`sudo apt-get install tesseract-ocr tesseract-ocr-eng` or `brew install tesseract`). The demo samples, paste-text mode and rule playground work without it.

## Run with Docker

```bash
docker build -t smartlabel .
docker run --rm -p 8501:8501 -v "$PWD/data:/app/data" smartlabel
```

The image bundles Tesseract, runs as a non-root user, and exposes a health check on `/_stcore/health`.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m compileall -q app.py smartlabel tests
python -m ruff check .
```

The same commands run in GitLab CI on every branch and merge request.

## Brand assets

`assets/logo.svg` and `assets/favicon.svg` are the source marks. The browser tab icon is rendered at runtime from the same design. To export static `favicon.ico` and PNG sizes for a hosting platform:

```bash
python -m smartlabel.branding
```

## Project layout

```text
app.py                         Streamlit entrypoint
smartlabel/ui.py               Pages, navigation and interactions
smartlabel/service.py          Workflow orchestration (text or images to result)
smartlabel/ocr.py              Tesseract adapter, line-aware with fallback pass
smartlabel/image.py            Image preparation
smartlabel/extraction.py       Field extraction with evidence text
smartlabel/rules.py            Deterministic checks and the rule registry
smartlabel/models.py           Shared data models, labels, serialisation
smartlabel/db.py               SQLite persistence
smartlabel/reports.py          JSON, HTML and PDF reports
smartlabel/demo.py             Prepared demo labels and synthetic images
smartlabel/branding.py         Runtime favicon, icon SVGs, favicon export
assets/                        Logo and favicon sources
tests/                         Unit tests
PROJECT_MEMORY.md              Progress log and context for future work
```

## Deployment

See `DEPLOYMENT.md`. For a public demo, connect the repository to Streamlit Community Cloud and keep `requirements.txt` and `packages.txt` at the root. For a multi-user deployment, move the database to PostgreSQL, add authentication and define an image-retention policy.

## Safety and scope

The rule set is intentionally small and visible. It must be reviewed against the current Legal Metrology (Packaged Commodities) Rules before any real production use. Do not upload private or regulated data to a public deployment until the privacy model is approved.
