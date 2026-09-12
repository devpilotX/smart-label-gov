"""Streamlit pages for SmartLabel Inspector.

The UI owns layout and interaction only. Extraction, rules, persistence and
reports live in their own modules and are called from here.
"""

from collections import Counter
from urllib.parse import quote

from . import __version__
from .branding import MAIL_ICON_SVG, WHATSAPP_ICON_SVG, favicon_image
from .config import (
    APP_NAME,
    APP_TAGLINE,
    ASSETS_DIR,
    DB_PATH,
    PRODUCT_CONTEXTS,
    RULE_SET_ID,
    SOLD_BY_OPTIONS,
    SUPPORTED_IMAGE_TYPES,
    ensure_data_dir,
)
from .db import Database
from .demo import DEFAULT_SAMPLE, DEMO_SAMPLES, demo_image_bytes
from .models import FIELD_LABELS, STATUS_LABELS, STATUS_ORDER, InspectionResult
from .ocr import tesseract_available
from .reports import html_bytes, json_bytes, pdf_bytes
from .rules import RULE_DEFINITIONS
from .service import screen_images, screen_text

_PAGES: dict[str, object] = {}

CHECK_STYLE = {
    "pass": ("success", ":material/check_circle:"),
    "review": ("warning", ":material/warning:"),
    "fail": ("error", ":material/error:"),
    "not_applicable": ("info", ":material/remove_circle:"),
}

REPORTS = (
    ("HTML", "HTML report", html_bytes, "text/html", "html", ":material/description:"),
    ("JSON", "JSON report", json_bytes, "application/json", "json", ":material/data_object:"),
    ("PDF", "PDF report", pdf_bytes, "application/pdf", "pdf", ":material/picture_as_pdf:"),
)

STEPS = (
    ("Capture", "Upload the front and back of the pack, use the camera, or paste the label text."),
    ("Read", "Tesseract OCR reads the visible text locally. Images never leave the machine."),
    ("Check", f"{len(RULE_DEFINITIONS)} transparent rules test the mandatory declarations."),
    ("Report", "Download JSON, HTML or PDF and share the summary in one tap."),
)

CSS = """
<style>
.block-container { max-width: 1240px; padding-top: 1.4rem; }
.sl-header { padding: 4px 0 18px; border-bottom: 1px solid #dce4ed; margin-bottom: 22px; }
.sl-kicker { color: #2167d5; font-weight: 700; letter-spacing: .12em; font-size: 11px; text-transform: uppercase; }
.sl-title { color: #17283d; font-size: 32px; line-height: 1.15; font-weight: 800; margin: 6px 0 4px; }
.sl-subtitle { color: #64748b; font-size: 15px; }
.sl-muted { color: #64748b; font-size: 13px; }
.sl-highlight { border-left: 4px solid #d79a00; background: #fff7d6; border-radius: 0 10px 10px 0; padding: 12px 16px; color: #795900; margin: 6px 0 14px; }
.sl-badge { display: inline-block; padding: 5px 14px; border-radius: 999px; font-weight: 700; font-size: 13px; }
.sl-badge-screened { background: #e3f7ef; color: #0f7a5c; }
.sl-badge-needs_attention { background: #fff3d6; color: #8a5a00; }
.sl-badge-potential_issue { background: #fde5e5; color: #a12c2c; }
.sl-result-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin: 4px 0 14px; }
.sl-share { display: flex; gap: 12px; flex-wrap: wrap; margin: 4px 0 10px; }
.sl-share-btn { display: inline-flex; align-items: center; gap: 9px; padding: 9px 16px; border-radius: 10px; font-weight: 600; font-size: 14px; text-decoration: none !important; border: 1px solid transparent; transition: filter .15s ease; }
.sl-share-btn:hover { filter: brightness(.94); }
.sl-share-btn svg { width: 18px; height: 18px; fill: currentColor; flex: none; }
.sl-wa { background: #25D366; color: #ffffff !important; }
.sl-mail { background: #ffffff; color: #17283d !important; border-color: #dce4ed; }
.sl-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }
.sl-dot-ok { background: #12b886; }
.sl-dot-warn { background: #f59f00; }
.sl-step-num { display: inline-flex; width: 28px; height: 28px; border-radius: 50%; background: #2167d5; color: #fff; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; margin-bottom: 8px; }
.sl-step-title { font-weight: 700; color: #17283d; margin-bottom: 4px; }
</style>
"""


# --------------------------------------------------------------------------- helpers


def _load_css(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _init_state(st) -> None:
    defaults = {"min_confidence": 0.70, "default_report": "HTML", "local_mode": True}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _header(st, kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="sl-header"><div class="sl-kicker">{kicker}</div>'
        f'<div class="sl-title">{title}</div><div class="sl-subtitle">{subtitle}</div></div>',
        unsafe_allow_html=True,
    )


def _status_counts(rows: list[dict]) -> dict[str, int]:
    counts = Counter(str(row.get("overall_status")) for row in rows)
    return {status: counts.get(status, 0) for status in STATUS_ORDER}


def _history_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "Inspection": row["inspection_id"],
            "Created (UTC)": str(row["created_at"]).replace("T", " ").replace("+00:00", ""),
            "Context": row["product_context"],
            "Sold by": row.get("sold_by", ""),
            "Source": str(row["source"]).replace("_", " "),
            "Status": STATUS_LABELS.get(row["overall_status"], row["overall_status"]),
        }
        for row in rows
    ]


def _run_demo(st, db: Database, sample_name: str) -> InspectionResult:
    sample = DEMO_SAMPLES[sample_name]
    result = screen_text(sample["text"], "prepared_demo", sample["product_context"], sample["sold_by"], 0.96)
    db.save(result)
    st.session_state["last_result"] = result
    st.session_state["last_image"] = demo_image_bytes(sample_name)
    return result


def _check_row(st, check) -> None:
    kind, icon = CHECK_STYLE.get(check.status, ("info", ":material/info:"))
    getattr(st, kind)(f"**{check.title}** \u00b7 {check.message}", icon=icon)


def _share_links(st, result: InspectionResult) -> None:
    summary = result.summary_text()
    whatsapp_url = "https://wa.me/?text=" + quote(summary)
    mail_url = "mailto:?subject=" + quote(f"SmartLabel report {result.inspection_id}") + "&body=" + quote(summary)
    st.markdown(
        '<div class="sl-share">'
        f'<a class="sl-share-btn sl-wa" href="{whatsapp_url}" target="_blank" rel="noopener">'
        f"{WHATSAPP_ICON_SVG}<span>Share on WhatsApp</span></a>"
        f'<a class="sl-share-btn sl-mail" href="{mail_url}" target="_blank" rel="noopener">'
        f"{MAIL_ICON_SVG}<span>Send by email</span></a>"
        "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("Copy summary text"):
        st.code(summary, language=None)


def _downloads(st, result: InspectionResult) -> None:
    default = st.session_state.get("default_report", "HTML")
    ordered = sorted(REPORTS, key=lambda item: item[0] != default)
    columns = st.columns(len(ordered))
    for column, (name, label, builder, mime, extension, icon) in zip(columns, ordered):
        try:
            data = builder(result)
        except Exception as exc:  # noqa: BLE001 - never let a report generator break the page
            column.caption(f"{name} report unavailable: {exc}")
            continue
        column.download_button(
            label,
            data=data,
            file_name=f"{result.inspection_id}.{extension}",
            mime=mime,
            icon=icon,
            type="primary" if name == default else "secondary",
            width="stretch",
            key=f"download_{name}_{result.inspection_id}",
        )


def _show_result(st, result: InspectionResult, image_bytes: bytes | None) -> None:
    status = result.overall_status
    created = result.created_at.replace("T", " ").replace("+00:00", " UTC")
    source = result.source.replace("_", " ")
    st.markdown(
        f'<div class="sl-result-head"><span class="sl-badge sl-badge-{status}">{result.status_label}</span>'
        f'<span class="sl-muted">Inspection <b>{result.inspection_id}</b> \u00b7 {created} \u00b7 {source} \u00b7 '
        f"{result.product_context}, sold by {result.sold_by.lower()}</span></div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Checks passed", f"{result.pass_count} / {result.applicable_count}", border=True)
    m2.metric("Needs attention", result.review_count, border=True)
    m3.metric("Fields detected", len(result.fields), border=True)
    m4.metric(
        "Confidence",
        f"{result.ocr_confidence:.0%}",
        border=True,
        help="Average OCR word confidence, or the assumed confidence for typed and demo text.",
    )

    for warning in result.warnings:
        st.warning(warning, icon=":material/warning:")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### Checks")
        for check in result.checks:
            _check_row(st, check)
    with right:
        st.markdown("##### Detected fields")
        minimum = float(st.session_state.get("min_confidence", 0.70))
        rows = [
            {
                "Field": FIELD_LABELS.get(name, name.replace("_", " ").title()),
                "Value": field.display_value,
                "Confidence": round(field.confidence * 100),
                "Evidence": field.source_text,
                "Flag": "Low confidence" if field.confidence < minimum else "",
            }
            for name, field in result.fields.items()
        ]
        if rows:
            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
                column_config={
                    "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=100, format="%d%%"),
                    "Evidence": st.column_config.TextColumn("Evidence", help="Exact text the value was read from"),
                },
            )
        else:
            st.info("No fields were extracted. Try a sharper, well-lit image or load a demo sample.", icon=":material/info:")
        if image_bytes:
            with st.expander("Prepared image used for OCR"):
                st.image(image_bytes, width="stretch")
        if result.raw_text:
            with st.expander("Raw text"):
                st.code(result.raw_text, language=None, wrap_lines=True)

    st.markdown("##### Reports and sharing")
    _downloads(st, result)
    _share_links(st, result)


def _sidebar_footer(st) -> None:
    ready = tesseract_available()
    dot = "sl-dot-ok" if ready else "sl-dot-warn"
    text = "Tesseract OCR ready" if ready else "Tesseract not found \u00b7 demo and text modes"
    with st.sidebar:
        st.divider()
        st.markdown(f'<div class="sl-muted"><span class="sl-dot {dot}"></span>{text}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sl-muted">{APP_TAGLINE} \u00b7 v{__version__} \u00b7 {RULE_SET_ID}</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------- pages


def dashboard() -> None:
    import streamlit as st

    db = Database(DB_PATH)
    _header(
        st,
        "Compliance workspace",
        APP_NAME,
        "Read a package label, check the mandatory declarations, and keep the evidence visible.",
    )
    recent = db.list_recent(500)
    counts = _status_counts(recent)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inspections", len(recent), border=True)
    c2.metric("Screened", counts["screened"], border=True)
    c3.metric("Needs attention", counts["needs_attention"], border=True)
    c4.metric("Potential issues", counts["potential_issue"], border=True)

    hero, side = st.columns([1.6, 1], gap="large")
    with hero.container(border=True):
        st.markdown("##### Start a screening")
        st.markdown(
            "Upload the front and back of a pack, or run a prepared sample to see the whole flow in under a minute."
        )
        b1, b2 = st.columns(2)
        if b1.button("New inspection", type="primary", icon=":material/document_scanner:", width="stretch"):
            st.switch_page(_PAGES["New inspection"])
        if b2.button("Run demo sample", icon=":material/science:", width="stretch"):
            _run_demo(st, db, DEFAULT_SAMPLE)
            st.switch_page(_PAGES["New inspection"])
    with side.container(border=True):
        st.markdown("##### System status")
        ready = tesseract_available()
        dot = "sl-dot-ok" if ready else "sl-dot-warn"
        ocr_text = "Tesseract OCR ready for images" if ready else "Tesseract not found. Demo, paste-text and rules still work."
        st.markdown(f'<div class="sl-muted"><span class="sl-dot {dot}"></span>{ocr_text}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sl-muted"><span class="sl-dot sl-dot-ok"></span>Rule set <code>{RULE_SET_ID}</code> \u00b7 '
            f"{len(RULE_DEFINITIONS)} checks</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="sl-muted"><span class="sl-dot sl-dot-ok"></span>Local SQLite history \u00b7 {len(recent)} saved</div>',
            unsafe_allow_html=True,
        )

    st.markdown("##### How it works")
    step_columns = st.columns(4)
    for index, (column, (title, text)) in enumerate(zip(step_columns, STEPS), start=1):
        with column.container(border=True):
            st.markdown(
                f'<div class="sl-step-num">{index}</div><div class="sl-step-title">{title}</div>'
                f'<div class="sl-muted">{text}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("##### Recent activity")
    if recent:
        st.dataframe(_history_rows(recent[:10]), width="stretch", hide_index=True)
    else:
        st.info("No inspections yet. Run the demo sample to see the full flow.", icon=":material/info:")


def new_inspection() -> None:
    import streamlit as st

    db = Database(DB_PATH)
    _header(
        st,
        "New inspection",
        "Screen a package label",
        "Upload the front and back of the pack, capture it with a camera, paste the label text, or load a prepared sample.",
    )
    ocr_ready = tesseract_available()
    if not ocr_ready:
        st.warning(
            "Tesseract OCR was not found on this machine. Demo samples and pasted text work without it. "
            "See Help for installation steps.",
            icon=":material/warning:",
        )

    camera_file = None
    with st.container(border=True):
        c1, c2 = st.columns(2)
        product_context = c1.selectbox(
            "Product context",
            PRODUCT_CONTEXTS,
            help="Changes which rules apply. Imported products need a country of origin; food products need an FSSAI licence.",
        )
        sold_by = c2.selectbox(
            "Sold by",
            SOLD_BY_OPTIONS,
            help="Used to confirm that the declared unit matches how the product is sold.",
        )

        upload_tab, camera_tab, text_tab, demo_tab = st.tabs(["Upload images", "Camera", "Paste text", "Demo samples"])
        with upload_tab:
            u1, u2 = st.columns(2)
            front_file = u1.file_uploader("Front label", type=SUPPORTED_IMAGE_TYPES, key="front_upload")
            back_file = u2.file_uploader("Back label (optional)", type=SUPPORTED_IMAGE_TYPES, key="back_upload")
            st.caption("Both sides are read together, so declarations printed on the back count.")
        with camera_tab:
            if st.toggle("Enable camera", key="camera_enabled", help="The browser asks for permission only when this is on."):
                camera_file = st.camera_input("Capture the label", key="camera_capture")
        with text_tab:
            pasted_text = st.text_area(
                "Label text",
                key="pasted_text",
                height=150,
                placeholder="MRP Rs. 120.00\nNet Qty: 500 g\nCustomer Care: 1800-123-4567\nManufactured by: ...",
            )
            st.caption("Useful when OCR is unavailable, or to test the rules on a transcription.")
        with demo_tab:
            sample_name = st.selectbox("Prepared sample", list(DEMO_SAMPLES), key="demo_sample")
            sample = DEMO_SAMPLES[sample_name]
            st.caption(f"{sample['description']} Runs as *{sample['product_context']}*, sold by {sample['sold_by'].lower()}.")
            load_demo = st.button("Load demo sample", icon=":material/science:", width="stretch")

        run = st.button("Run screening", type="primary", icon=":material/play_arrow:", width="stretch")

    if load_demo:
        _run_demo(st, db, sample_name)
        st.toast("Demo sample screened", icon=":material/check_circle:")

    if run:
        uploads = [file for file in (front_file, back_file, camera_file) if file is not None]
        text = (pasted_text or "").strip()
        if uploads and not ocr_ready:
            st.error(
                "Tesseract is required to read images. Install it, or use Paste text or a demo sample.",
                icon=":material/error:",
            )
        elif uploads:
            with st.spinner("Reading the label with OCR...", show_time=True):
                try:
                    result, prepared = screen_images([file.getvalue() for file in uploads], product_context, sold_by)
                except Exception as exc:  # noqa: BLE001 - surface any OCR failure to the user
                    st.error(f"Screening could not run: {exc}", icon=":material/error:")
                else:
                    if camera_file is not None and len(uploads) == 1:
                        result.source = "camera"
                    db.save(result)
                    st.session_state["last_result"] = result
                    st.session_state["last_image"] = prepared
                    st.toast("Screening complete", icon=":material/check_circle:")
        elif text:
            result = screen_text(text, "pasted_text", product_context, sold_by)
            db.save(result)
            st.session_state["last_result"] = result
            st.session_state["last_image"] = None
            st.toast("Text screened", icon=":material/check_circle:")
        else:
            st.error(
                "Add a label image, enable the camera, paste text, or load a demo sample first.",
                icon=":material/error:",
            )

    result = st.session_state.get("last_result")
    if result is not None:
        st.divider()
        _show_result(st, result, st.session_state.get("last_image"))


def history() -> None:
    import streamlit as st

    db = Database(DB_PATH)
    _header(st, "History", "Inspection history", "Every saved screening stays traceable by date, source, context, and status.")
    rows = db.list_recent(500)
    if not rows:
        st.info("No saved inspections yet. Run a screening or a demo sample first.", icon=":material/info:")
        return

    f1, f2 = st.columns([2, 1])
    query = f1.text_input(
        "Search",
        placeholder="Search by inspection ID, source, context, or status",
        label_visibility="collapsed",
    )
    status_filter = f2.multiselect(
        "Status",
        [STATUS_LABELS[status] for status in STATUS_ORDER],
        placeholder="All statuses",
        label_visibility="collapsed",
    )
    display = _history_rows(rows)
    if query:
        needle = query.lower()
        display = [row for row in display if needle in " ".join(str(value) for value in row.values()).lower()]
    if status_filter:
        display = [row for row in display if row["Status"] in status_filter]
    st.caption(f"{len(display)} of {len(rows)} inspections")
    st.dataframe(display, width="stretch", hide_index=True)

    st.markdown("##### Inspection details")
    selected = st.selectbox(
        "Open an inspection",
        [row["Inspection"] for row in display],
        index=None,
        placeholder="Choose an inspection ID to view the saved evidence and re-download reports",
    )
    if selected:
        payload = db.get(selected)
        if payload:
            _show_result(st, InspectionResult.from_dict(payload), None)
        else:
            st.error("That inspection could not be loaded.", icon=":material/error:")


def rule_sets() -> None:
    import streamlit as st

    _header(
        st,
        "Rule sets",
        "Screening rules",
        "Small, visible, deterministic, and covered by tests. Every status comes with a plain-language reason.",
    )
    st.markdown(f"**Active rule set:** `{RULE_SET_ID}` \u00b7 {len(RULE_DEFINITIONS)} checks")
    st.dataframe(
        [
            {"Code": rule["code"], "Check": rule["title"], "What it verifies": rule["check"], "Applies to": rule["applies"]}
            for rule in RULE_DEFINITIONS
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown("##### How a status is decided")
    s1, s2, s3, s4 = st.columns(4)
    s1.success("**Pass**: declaration found and numeric tests succeed.", icon=":material/check_circle:")
    s2.warning("**Review**: not found with enough confidence.", icon=":material/warning:")
    s3.error("**Fail**: found, but breaks a numeric rule.", icon=":material/error:")
    s4.info("**Not applicable**: the rule does not apply to this context.", icon=":material/remove_circle:")

    st.markdown("##### Try the rules on text")
    with st.container(border=True):
        text = st.text_area(
            "Label text",
            key="rule_playground_text",
            height=140,
            placeholder="Paste or type the declarations exactly as printed on a pack.",
        )
        p1, p2, p3 = st.columns(3, vertical_alignment="bottom")
        context = p1.selectbox("Product context", PRODUCT_CONTEXTS, key="rule_playground_context")
        sold_by = p2.selectbox("Sold by", SOLD_BY_OPTIONS, key="rule_playground_sold_by")
        evaluate = p3.button("Evaluate", icon=":material/rule:", width="stretch")
    if evaluate:
        if not text.strip():
            st.error("Enter some label text first.", icon=":material/error:")
        else:
            result = screen_text(text, "rule_playground", context, sold_by)
            for check in result.checks:
                _check_row(st, check)
            st.caption("Playground results are not saved to history.")

    st.info(
        "This is a screening aid. The rule set must be reviewed against the current Legal Metrology "
        "(Packaged Commodities) Rules before production use.",
        icon=":material/info:",
    )


def analytics() -> None:
    import pandas as pd
    import streamlit as st

    db = Database(DB_PATH)
    _header(st, "Analytics", "Screening overview", "Where labels pass, where they need attention, and how the workload moves.")
    rows = db.list_recent(1000)
    if not rows:
        st.info("Run a few inspections to see charts here.", icon=":material/info:")
        return

    counts = _status_counts(rows)
    total = len(rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total inspections", total, border=True)
    c2.metric("Screened", counts["screened"], border=True)
    c3.metric("Needs attention", counts["needs_attention"], border=True)
    c4.metric("Screened rate", f"{counts['screened'] / total:.0%}", border=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### Outcomes")
        status_frame = pd.DataFrame(
            {"Status": [STATUS_LABELS[status] for status in STATUS_ORDER], "Count": [counts[status] for status in STATUS_ORDER]}
        )
        st.bar_chart(status_frame, x="Status", y="Count", color="#2167d5", height=280)
    with right:
        st.markdown("##### Inspections per day")
        per_day = Counter(str(row["created_at"])[:10] for row in rows)
        days = sorted(per_day)
        day_frame = pd.DataFrame({"Day": days, "Inspections": [per_day[day] for day in days]})
        st.bar_chart(day_frame, x="Day", y="Inspections", color="#12b886", height=280)

    st.markdown("##### Where labels need attention")
    tally: Counter = Counter()
    for payload in db.list_payloads(500):
        for check in payload.get("checks", []):
            status = str(check.get("status", ""))
            if status in {"pass", "review", "fail"}:
                tally[(str(check.get("title", "")), status.title())] += 1
    if tally:
        check_frame = pd.DataFrame([{"Check": title, "Status": status, "Count": count} for (title, status), count in tally.items()])
        st.bar_chart(check_frame, x="Check", y="Count", color="Status", height=320)
    else:
        st.caption("Check-level statistics appear once inspections with rule results are saved.")


def project_brief() -> None:
    import streamlit as st

    _header(st, "Project brief", "Why SmartLabel Inspector", "A focused product for a real review problem.")
    left, right = st.columns(2, gap="large")
    with left.container(border=True):
        st.markdown("##### The problem")
        st.markdown(
            "Every packaged product sold in India must carry a fixed set of declarations: MRP, net quantity, "
            "manufacturer or packer, date of packing, consumer care details and, for imports, the country of origin. "
            "Checking them today is manual, slow and leaves no evidence trail."
        )
    with right.container(border=True):
        st.markdown("##### The solution")
        st.markdown(
            "Photograph the pack. Local OCR reads it, deterministic rules test each declaration, and every value is "
            "shown with its confidence and the exact text it came from. Results are saved, exportable and shareable."
        )

    st.markdown("##### What makes it different")
    d1, d2, d3, d4 = st.columns(4)
    for column, (title, text) in zip(
        (d1, d2, d3, d4),
        (
            ("Evidence-led", "Field, confidence, source text and rule message on every result."),
            ("Deterministic", "No black box. Rules are small, visible, versioned and unit-tested."),
            ("Local-first", "Runs offline on a laptop. Images never leave the machine."),
            ("Ready to share", "JSON, HTML and PDF reports plus WhatsApp and email summaries."),
        ),
    ):
        with column.container(border=True):
            st.markdown(f'<div class="sl-step-title">{title}</div><div class="sl-muted">{text}</div>', unsafe_allow_html=True)

    st.markdown("##### Stack")
    st.table(
        [
            {"Layer": "Interface", "Technology": "Streamlit with Material icon navigation"},
            {"Layer": "Application", "Technology": "Python 3.11+, typed dataclasses"},
            {"Layer": "OCR", "Technology": "Tesseract via pytesseract, line-aware with fallback segmentation"},
            {"Layer": "Image", "Technology": "Pillow preparation pipeline"},
            {"Layer": "Rules", "Technology": f"{len(RULE_DEFINITIONS)} deterministic checks, rule set {RULE_SET_ID}"},
            {"Layer": "Database", "Technology": "SQLite (PostgreSQL adapter planned)"},
            {"Layer": "Reports", "Technology": "JSON, HTML and PDF (reportlab)"},
            {"Layer": "Quality", "Technology": "Unit tests, ruff, GitLab CI, Docker health check"},
        ]
    )

    st.markdown("##### Roadmap")
    st.markdown(
        "1. Annotated evidence boxes drawn from OCR word coordinates.\n"
        "2. Multilingual OCR once the English workflow is stable.\n"
        "3. Versioned rule sets with per-rule tests and an audit log.\n"
        "4. PostgreSQL, authentication and a review queue for teams."
    )


def help_page() -> None:
    import streamlit as st

    _header(st, "Help", "Getting the best result", "Short answers for inspectors, demo presenters, and developers.")
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("##### Taking a good label photo")
            st.markdown(
                "- Fill the frame with the declaration panel and keep the label flat.\n"
                "- Use even light and avoid glare on glossy film.\n"
                "- Hold the camera square to the pack; skewed text lowers OCR confidence.\n"
                "- Upload the back panel too; many declarations are printed there."
            )
        with st.container(border=True):
            st.markdown("##### Reading a result")
            st.markdown(
                "- **Pass**: the declaration was found and any numeric test succeeded.\n"
                "- **Review**: the declaration was not found with enough confidence. Check the pack manually.\n"
                "- **Fail**: a value was found but breaks a numeric rule, for example an MRP of zero.\n"
                "- **Not applicable**: the rule does not apply to the selected product context."
            )
    with right:
        with st.container(border=True):
            st.markdown("##### Installing Tesseract OCR")
            st.markdown("Ubuntu or Debian")
            st.code("sudo apt-get install tesseract-ocr tesseract-ocr-eng", language="bash")
            st.markdown("macOS")
            st.code("brew install tesseract", language="bash")
            st.markdown("Windows")
            st.markdown("Install a Tesseract build for Windows, add its folder to PATH, then restart the app.")
        with st.container(border=True):
            st.markdown("##### Frequently asked")
            with st.expander("Does this issue a legal certificate?"):
                st.markdown(
                    "No. SmartLabel Inspector is a screening aid. It highlights what is visible and what is missing so a "
                    "qualified person can decide faster."
                )
            with st.expander("Where are my images stored?"):
                st.markdown(
                    "Images are processed in memory and discarded. Only the structured result, the extracted text and "
                    "the rule outcomes are saved in the local SQLite database."
                )
            with st.expander("Can I add or change rules?"):
                st.markdown(
                    "Yes. Rules live in `smartlabel/rules.py` with a registry that drives the Rule sets page. Add a test in "
                    "`tests/test_rules.py` whenever a rule changes."
                )
            with st.expander("Which formats can I export?"):
                st.markdown("JSON for systems, HTML for browsers and printing, PDF for filing. All come from the same result.")


def settings() -> None:
    import streamlit as st

    db = Database(DB_PATH)
    _header(st, "Settings", "Workspace settings", "Local-first defaults. Changes apply immediately to this session.")
    with st.container(border=True):
        st.markdown("##### Screening")
        st.toggle(
            "Local processing mode",
            key="local_mode",
            help="Images are processed on this machine and only the structured result is stored.",
        )
        st.slider(
            "Minimum confidence to trust a field",
            0.50,
            0.99,
            key="min_confidence",
            step=0.01,
            format="%.2f",
            help="Fields below this confidence are flagged in the results table.",
        )
        st.selectbox(
            "Default report format",
            ["HTML", "JSON", "PDF"],
            key="default_report",
            help="Shown first and highlighted in the results.",
        )
    with st.container(border=True):
        st.markdown("##### Data")
        st.markdown(
            f'<div class="sl-muted">SQLite database: <code>{DB_PATH}</code> \u00b7 {db.count()} saved inspections</div>',
            unsafe_allow_html=True,
        )
        st.caption("Override the location with the SMARTLABEL_DB_PATH environment variable.")
        confirm = st.checkbox("I understand this permanently deletes all saved inspections")
        if st.button("Clear history", icon=":material/delete:", disabled=not confirm):
            deleted = db.clear()
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_image", None)
            st.success(f"History cleared. {deleted} inspections removed.", icon=":material/check_circle:")
    st.markdown(
        '<div class="sl-highlight"><b>Current scope</b><br>English OCR, transparent checks, SQLite history, '
        "JSON, HTML and PDF reports, and one-tap sharing.</div>",
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- entrypoint


def run_app() -> None:
    import streamlit as st

    try:
        page_icon = favicon_image(128)
    except Exception:  # noqa: BLE001 - fall back to the static SVG if Pillow is unavailable
        page_icon = str(ASSETS_DIR / "favicon.svg")

    st.set_page_config(
        page_title=APP_NAME,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get help": None,
            "Report a bug": None,
            "About": f"**{APP_NAME}** v{__version__}  \n{APP_TAGLINE}. Screening aid only, not a legal certificate.",
        },
    )
    ensure_data_dir()
    _init_state(st)
    _load_css(st)
    st.logo(str(ASSETS_DIR / "logo.svg"), size="large", icon_image=str(ASSETS_DIR / "favicon.svg"))

    sections = {
        "Workspace": [
            st.Page(dashboard, title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page(new_inspection, title="New inspection", icon=":material/document_scanner:"),
            st.Page(history, title="History", icon=":material/history:"),
        ],
        "Insight": [
            st.Page(rule_sets, title="Rule sets", icon=":material/rule:"),
            st.Page(analytics, title="Analytics", icon=":material/analytics:"),
        ],
        "About": [
            st.Page(project_brief, title="Project brief", icon=":material/info:"),
            st.Page(help_page, title="Help", icon=":material/help:"),
            st.Page(settings, title="Settings", icon=":material/settings:"),
        ],
    }
    _PAGES.clear()
    for pages in sections.values():
        for page in pages:
            _PAGES[page.title] = page

    navigation = st.navigation(sections)
    _sidebar_footer(st)
    navigation.run()
