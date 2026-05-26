import importlib.util
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import ai_agent
import database as db
import screen_bot
import stt_engine
import tts_engine


load_dotenv()

APP_TAGLINE = "One-call-at-a-time local AI calling assistant for personal demos and workflow prototyping."

BUSINESS_SCRIPT_DEFAULT = (
    "Hi, this is an AI assistant calling on behalf of [Business Name]. "
    "I'm reaching out to see if you might be interested in [offer]. "
    "Is this a good time for a quick question?"
)

AI_BEHAVIOR_DEFAULT = (
    "Keep replies short, natural, and polite. Ask one question at a time. "
    "Never pressure the person. If they ask, disclose that you are an automated assistant."
)

SAFETY_WARNING = (
    "Demo only. Do not use for spam, robocalling, or calling people without permission. "
    "Google Voice browser automation may violate the Google Voice Acceptable Use Policy. "
    "Use one-by-one manual starts, honor DNC requests immediately, and follow all applicable laws."
)

STATUSES = [
    "interested",
    "not_interested",
    "callback",
    "dnc",
    "wrong_number",
    "busy",
    "continue",
    "completed",
]

DNC_PHRASES = [
    "remove me",
    "do not call",
    "don't call",
    "dont call",
    "stop calling",
]

WRONG_NUMBER_PHRASES = ["wrong number"]
NOT_INTERESTED_PHRASES = ["not interested"]


def apply_dark_theme():
    st.markdown(
        """
<style>
    :root {
        --bg: #070b12;
        --panel: #101826;
        --panel-2: #121d2f;
        --text: #e5edf7;
        --muted: #9aa8ba;
        --line: #243044;
        --accent: #38bdf8;
        --accent-2: #22c55e;
        --danger: #f97373;
    }

    .stApp {
        background:
            radial-gradient(circle at 20% 0%, rgba(56, 189, 248, 0.10), transparent 28rem),
            linear-gradient(135deg, #070b12 0%, #0b1220 55%, #0a0f1a 100%);
        color: var(--text);
    }

    [data-testid="stSidebar"] {
        background: #080d16;
        border-right: 1px solid var(--line);
    }

    h1, h2, h3 {
        letter-spacing: 0;
    }

    .portfolio-hero {
        padding: 1.4rem 1.6rem;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: linear-gradient(135deg, rgba(16, 24, 38, 0.96), rgba(18, 29, 47, 0.90));
        margin-bottom: 1rem;
    }

    .portfolio-hero h1 {
        margin: 0 0 0.35rem 0;
        font-size: 2.1rem;
    }

    .portfolio-hero p {
        color: var(--muted);
        margin: 0;
        max-width: 62rem;
    }

    .metric-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: rgba(16, 24, 38, 0.92);
        padding: 1rem;
        min-height: 112px;
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.45rem;
    }

    .metric-value {
        color: var(--text);
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.1;
    }

    .metric-help {
        color: var(--muted);
        font-size: 0.85rem;
        margin-top: 0.35rem;
    }

    .status-pill {
        display: inline-block;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        background: rgba(56, 189, 248, 0.10);
        color: var(--text);
        font-size: 0.82rem;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
    }

    .stButton > button {
        border-radius: 7px;
        border: 1px solid #2c3b52;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def init_state():
    db.init_db()
    defaults = {
        "active_lead_id": None,
        "active_call_id": None,
        "conversation": [],
        "last_ai_reply": "",
        "last_ai_status": "continue",
        "last_ai_summary": "",
        "customer_said_input": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def load_settings():
    config = screen_bot.load_config()
    return {
        "business_name": db.get_setting("business_name", "[Business Name]"),
        "offer": db.get_setting("offer", "[offer]"),
        "opening_script": db.get_setting("opening_script", db.get_setting("business_script", BUSINESS_SCRIPT_DEFAULT)),
        "ai_behavior_instructions": db.get_setting("ai_behavior_instructions", AI_BEHAVIOR_DEFAULT),
        "tts_voice": config.get("tts_voice") or db.get_setting("tts_voice", tts_engine.DEFAULT_VOICE),
        "selected_input_device": config.get("selected_input_device"),
        "selected_output_device": config.get("selected_output_device"),
        "recording_seconds": int(config.get("recording_seconds") or 5),
        "call_delay_seconds": int(db.get_setting("call_delay_seconds", "10")),
        "daily_call_limit": int(db.get_setting("daily_call_limit", "20")),
    }


def save_settings(settings):
    for key, value in settings.items():
        db.set_setting(key, str(value))


def save_audio_config(selected_input_device=None, selected_output_device=None, recording_seconds=5, tts_voice=None):
    config = screen_bot.load_config()
    config["selected_input_device"] = selected_input_device
    config["selected_output_device"] = selected_output_device
    config["recording_seconds"] = int(recording_seconds)
    if tts_voice:
        config["tts_voice"] = tts_voice
        db.set_setting("tts_voice", tts_voice)
    screen_bot.save_config(config)


def now_timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def add_message(role, message):
    st.session_state.conversation.append(
        {
            "role": role,
            "speaker": role,
            "message": message,
            "text": message,
            "timestamp": now_timestamp(),
        }
    )


def render_opening_script(settings):
    return (
        settings["opening_script"]
        .replace("[Business Name]", settings["business_name"])
        .replace("[offer]", settings["offer"])
    )


def warning_banner():
    st.error(SAFETY_WARNING)


def portfolio_header(title="AI Google Voice Calling Assistant", subtitle=APP_TAGLINE):
    st.markdown(
        f"""
<div class="portfolio-hero">
    <h1>{title}</h1>
    <p>{subtitle}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def metric_card(label, value, help_text=""):
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">{label}</div>
    <div class="metric-value">{value}</div>
    <div class="metric-help">{help_text}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def system_check_sidebar():
    st.sidebar.subheader("System Check")
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    st.sidebar.write(f"Python: {version}")
    if sys.version_info[:2] != (3, 12):
        st.sidebar.warning("Use Python 3.12 for the smoothest Windows installs.")

    st.sidebar.write(f"Streamlit available: {importlib.util.find_spec('streamlit') is not None}")
    st.sidebar.write(f"sounddevice available: {importlib.util.find_spec('sounddevice') is not None}")
    st.sidebar.write(f"Groq key loaded: {bool(os.getenv('GROQ_API_KEY'))}")
    st.sidebar.write(f"config.json exists: {Path('config.json').exists()}")
    st.sidebar.write(f"database file exists: {db.DB_PATH.exists()}")


def selected_lead_widget(leads_df, key="lead_select"):
    if leads_df.empty:
        st.info("Upload leads before starting a call.")
        return None

    options = {}
    for row in leads_df.itertuples():
        dnc_label = " - DNC" if getattr(row, "dnc", 0) else ""
        options[f"#{row.id} - {row.name or 'Unknown'} - {row.phone} - {row.status}{dnc_label}"] = int(row.id)
    label = st.selectbox("Select lead", list(options.keys()), key=key)
    return options[label]


def dataframe_csv(df):
    if df.empty:
        return "".encode("utf-8")
    return df.to_csv(index=False).encode("utf-8")


def status_counts(leads):
    if leads.empty or "status" not in leads.columns:
        return {}
    return leads["status"].fillna("new").value_counts().to_dict()


def call_status_counts(calls):
    if calls.empty or "status" not in calls.columns:
        return {}
    return calls["status"].fillna("unknown").value_counts().to_dict()


def analytics_summary():
    leads = db.get_leads(include_dnc=True)
    calls = db.get_calls()
    lead_counts = status_counts(leads)
    call_counts = call_status_counts(calls)
    dnc_count = int(leads["dnc"].sum()) if not leads.empty and "dnc" in leads.columns else 0
    today_calls = db.count_calls_on_date(date.today().isoformat())
    return {
        "leads": leads,
        "calls": calls,
        "lead_counts": lead_counts,
        "call_counts": call_counts,
        "total_leads": len(leads),
        "total_calls": len(calls),
        "interested": lead_counts.get("interested", 0),
        "callbacks": lead_counts.get("callback", 0),
        "dnc": dnc_count,
        "completed": call_counts.get("completed", 0),
        "today_calls": today_calls,
    }


def filtered_leads(leads, search_text, statuses, include_dnc):
    if leads.empty:
        return leads

    filtered = leads.copy()
    if not include_dnc and "dnc" in filtered.columns:
        filtered = filtered[filtered["dnc"] == 0]

    if statuses:
        filtered = filtered[filtered["status"].fillna("new").isin(statuses)]

    search = search_text.strip().lower()
    if search:
        fields = ["name", "phone", "company", "status"]
        mask = pd.Series(False, index=filtered.index)
        for field in fields:
            if field in filtered.columns:
                mask = mask | filtered[field].fillna("").astype(str).str.lower().str.contains(search, regex=False)
        filtered = filtered[mask]

    return filtered


def render_lead_table(leads):
    if leads.empty:
        st.info("No leads match the current filters.")
        return

    columns = ["id", "name", "phone", "company", "email", "status", "dnc", "updated_at", "notes"]
    visible = [column for column in columns if column in leads.columns]
    st.dataframe(
        leads[visible],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "name": st.column_config.TextColumn("Name", width="medium"),
            "phone": st.column_config.TextColumn("Phone", width="medium"),
            "company": st.column_config.TextColumn("Company", width="medium"),
            "email": st.column_config.TextColumn("Email", width="medium"),
            "status": st.column_config.TextColumn("Status", width="small"),
            "dnc": st.column_config.CheckboxColumn("DNC", width="small"),
            "updated_at": st.column_config.TextColumn("Updated", width="medium"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        },
    )


def device_label(device):
    if device is None:
        return "Default"
    return f"{device['index']} - {device['name']}"


def selected_device_from_label(label):
    if not label or label == "Default":
        return None
    try:
        return int(label.split(" - ", 1)[0])
    except (ValueError, IndexError):
        return None


def device_labels(devices):
    return ["Default"] + [device_label(device) for device in devices]


def device_index_for_select(labels, selected_index):
    if selected_index is None:
        return 0
    for index, label in enumerate(labels):
        if label.startswith(f"{selected_index} - "):
            return index
    return 0


def capture_coordinate(config_key, label):
    with st.spinner("Move your mouse to the target in Google Voice. Capturing in 3 seconds..."):
        time.sleep(3)
        pos = screen_bot.capture_position()
        screen_bot.save_coordinate(config_key, pos)
    st.success(f"Saved {label}: x={pos[0]}, y={pos[1]}")


def setup_coordinates_page():
    st.header("Setup Coordinates")
    st.write("Open Google Voice in Chrome first, then capture each button or input location.")
    st.info(screen_bot.get_failsafe_message())

    config = screen_bot.load_config()
    st.json(config)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Capture Number Input Coordinate", use_container_width=True):
            capture_coordinate("number_input", "number input")
        if st.button("Test Click Number Input", use_container_width=True):
            screen_bot.click_number_input()
            st.success("Clicked number input.")

    with col2:
        if st.button("Capture Call Button Coordinate", use_container_width=True):
            capture_coordinate("call_button", "call button")
        if st.button("Test Click Call Button", use_container_width=True):
            screen_bot.click_call()
            st.success("Clicked call button.")

    with col3:
        if st.button("Capture End Call Button Coordinate", use_container_width=True):
            capture_coordinate("end_call_button", "end call button")
        if st.button("Test Click End Button", use_container_width=True):
            screen_bot.click_end()
            st.success("Clicked end call button.")

    with st.expander("Optional keypad/clear coordinate"):
        if st.button("Capture Keypad / Clear Coordinate"):
            capture_coordinate("keypad_clear", "keypad / clear button")


def dashboard_page(settings):
    portfolio_header()
    st.caption("Portfolio build: Streamlit, SQLite, Groq, Edge TTS, PyAutoGUI, optional local audio capture.")
    warning_banner()

    summary = analytics_summary()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total leads", summary["total_leads"], "CSV-backed CRM records")
    with col2:
        metric_card("Total calls", summary["total_calls"], f"{summary['today_calls']} logged today")
    with col3:
        metric_card("Interested", summary["interested"], "Qualified positive outcomes")
    with col4:
        metric_card("Callbacks", summary["callbacks"], "Follow-up opportunities")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        metric_card("DNC", summary["dnc"], "Removal requests honored")
    with col6:
        metric_card("Completed", summary["completed"], "Calls ended and saved")
    with col7:
        metric_card("Daily limit", settings["daily_call_limit"], "Safety throttle")
    with col8:
        metric_card("Delay", f"{settings['call_delay_seconds']}s", "Between manual calls")

    st.subheader("Lead Status Mix")
    if summary["lead_counts"]:
        pills = "".join(
            f"<span class='status-pill'>{status}: {count}</span>"
            for status, count in sorted(summary["lead_counts"].items())
        )
        st.markdown(pills, unsafe_allow_html=True)
    else:
        st.info("No leads imported yet.")

    col_recent, col_notes = st.columns([2, 1])
    with col_recent:
        st.subheader("Recent Calls")
        calls = summary["calls"]
        if calls.empty:
            st.info("No call history yet.")
        else:
            st.dataframe(calls.head(8), use_container_width=True, hide_index=True)
    with col_notes:
        st.subheader("Safety Model")
        st.write("Manual start is required for every call.")
        st.write("Only CSV-imported leads can be called.")
        st.write("DNC and removal phrases are handled immediately.")
        st.write("No full-list or unattended dialing is included.")


def crm_leads_page():
    st.header("Leads CRM")
    st.write("Import, search, filter, review, and export leads. Calls remain one selected lead at a time.")

    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded).fillna("")
        required = ["name", "phone", "company", "email", "notes"]
        missing = set(required) - set(df.columns)
        if missing:
            st.error(f"Missing columns: {', '.join(sorted(missing))}")
            return

        st.dataframe(df[required], use_container_width=True)
        if st.button("Save Leads to SQLite", type="primary"):
            count = db.upsert_leads(df[required])
            st.success(f"Saved {count} leads.")

    leads = db.get_leads(include_dnc=True)
    st.subheader("Lead Pipeline")
    if leads.empty:
        st.info("No leads yet. Upload a CSV with name, phone, company, email, notes.")
        return

    search_col, status_col, dnc_col = st.columns([2, 2, 1])
    with search_col:
        search_text = st.text_input("Search by name, phone, company, or status", key="lead_search")
    with status_col:
        statuses = sorted(leads["status"].fillna("new").unique().tolist())
        selected_statuses = st.multiselect("Filter status", statuses)
    with dnc_col:
        include_dnc = st.checkbox("Include DNC", value=True)

    filtered = filtered_leads(leads, search_text, selected_statuses, include_dnc)
    st.caption(f"Showing {len(filtered)} of {len(leads)} leads.")
    render_lead_table(filtered)
    st.download_button(
        "Export filtered leads as CSV",
        data=dataframe_csv(filtered),
        file_name="leads_export.csv",
        mime="text/csv",
    )


def lead_detail_page(settings):
    st.header("Lead Detail")
    leads = db.get_leads(include_dnc=True)
    lead_id = selected_lead_widget(leads, "lead_detail_select")
    if lead_id is None:
        return

    lead = db.get_lead(lead_id)
    if not lead:
        st.error("Lead not found.")
        return

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader(lead["name"] or "Unknown lead")
        st.write(f"Phone: {lead['phone']}")
        st.write(f"Company: {lead['company'] or 'Not provided'}")
        st.write(f"Email: {lead['email'] or 'Not provided'}")
        st.write(f"Status: {lead['status']}")
        st.write(f"DNC: {'Yes' if lead['dnc'] else 'No'}")
        st.text_area("Notes", lead["notes"] or "", height=140, disabled=True)
    with right:
        st.subheader("Actions")
        status_choice = st.selectbox("Update status", STATUSES, index=STATUSES.index(lead["status"]) if lead["status"] in STATUSES else 6)
        if st.button("Save Status", use_container_width=True):
            update_selected_status(lead_id, status_choice, "Updated from lead detail page.")
            st.success(f"Saved status: {status_choice}")

        if st.button("Mark DNC", use_container_width=True):
            update_selected_status(lead_id, "dnc", "Marked DNC from lead detail page.")
            st.warning("Lead marked DNC.")

        confirmed = st.checkbox("Confirm this CSV lead is allowed to be called.", key="detail_confirm")
        if st.button("Start One Call", type="primary", use_container_width=True):
            start_call_for_lead(lead_id, settings, confirmed)

    calls = db.get_calls()
    st.subheader("Lead Call History")
    if calls.empty:
        st.info("No call history yet.")
        return
    related = calls[calls["lead_id"] == lead_id] if "lead_id" in calls.columns else pd.DataFrame()
    if related.empty:
        st.info("No calls recorded for this lead.")
    else:
        st.dataframe(related, use_container_width=True, hide_index=True)


def can_start_call(settings):
    if st.session_state.active_call_id:
        return False, "A call is already active. End or save it before starting another."

    today_count = db.count_calls_on_date(date.today().isoformat())
    if today_count >= settings["daily_call_limit"]:
        return False, f"Daily call limit reached: {today_count}/{settings['daily_call_limit']}."

    last_started = db.get_setting("last_call_started_at", "")
    if last_started:
        remaining = db.seconds_until_delay_passed(last_started, settings["call_delay_seconds"])
        if remaining > 0:
            return False, f"Call delay active. Wait {remaining} more seconds."

    return True, ""


def countdown_before_dial():
    placeholder = st.empty()
    for remaining in range(5, 0, -1):
        placeholder.warning(f"Dialing in {remaining} seconds. {screen_bot.get_failsafe_message()}")
        time.sleep(1)
    placeholder.empty()


def start_call_for_lead(lead_id, settings, confirmed):
    if not confirmed:
        st.warning("Check the confirmation box before dialing.")
        return

    lead = db.get_lead(lead_id)
    if not lead:
        st.error("Lead not found.")
        return
    if lead["dnc"]:
        st.error("This lead is marked DNC. It will not be called.")
        return

    allowed, reason = can_start_call(settings)
    if not allowed:
        st.warning(reason)
        return

    call_id = db.start_call(lead_id, lead["phone"])
    db.set_setting("last_call_started_at", db.now_iso())

    st.session_state.active_lead_id = lead_id
    st.session_state.active_call_id = call_id
    st.session_state.conversation = []
    st.session_state.last_ai_reply = ""
    st.session_state.last_ai_status = "continue"
    st.session_state.last_ai_summary = ""

    try:
        countdown_before_dial()
        screen_bot.call_number(lead["phone"])
        st.success(f"Started call for {lead['name'] or lead['phone']}.")
    except Exception as exc:
        db.end_call(call_id, "continue", transcript_text(), f"Dialing failed: {exc}")
        st.session_state.active_call_id = None
        st.error(f"Dialing failed: {exc}")


def update_selected_status(lead_id, status, summary="Manually classified."):
    if status == "dnc":
        db.mark_dnc(lead_id)
    else:
        db.update_lead_status(lead_id, status)
    st.session_state.last_ai_status = status
    st.session_state.last_ai_summary = summary
    if st.session_state.active_call_id:
        db.update_call(st.session_state.active_call_id, status, transcript_text(), summary)


def end_current_call():
    if not st.session_state.active_call_id:
        st.info("No active call to end.")
        return

    try:
        screen_bot.click_end()
    except Exception as exc:
        st.warning(f"Could not click the end button automatically: {exc}")

    status = st.session_state.last_ai_status
    if status == "continue":
        status = "completed"
    db.end_call(st.session_state.active_call_id, status, transcript_text(), st.session_state.last_ai_summary)
    if st.session_state.active_lead_id and status != "dnc":
        db.update_lead_status(st.session_state.active_lead_id, status)
    st.session_state.active_call_id = None
    st.session_state.last_ai_status = status
    st.success("Call ended and history saved.")


def save_current_transcript():
    if not st.session_state.active_call_id:
        st.info("No active call to save.")
        return
    db.update_call(
        st.session_state.active_call_id,
        st.session_state.last_ai_status,
        transcript_text(),
        st.session_state.last_ai_summary,
    )
    st.success("Transcript saved.")


def campaign_control_page(settings):
    st.header("Campaign Control")
    st.write("Calls are one lead at a time. Confirm and press Start Call manually before every call.")

    leads = db.get_leads()
    lead_id = selected_lead_widget(leads, "campaign_lead_select")
    if lead_id is None:
        return

    today_count = db.count_calls_on_date(date.today().isoformat())
    st.caption(f"Today's calls: {today_count}/{settings['daily_call_limit']}. Delay between calls: {settings['call_delay_seconds']} seconds.")
    st.dataframe(leads, use_container_width=True)

    confirmed = st.checkbox("I confirm this selected lead came from the uploaded CSV and is allowed to be called.", key="campaign_confirm")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Start Call", type="primary", use_container_width=True):
            start_call_for_lead(lead_id, settings, confirmed)
        if st.button("Mark interested", use_container_width=True):
            update_selected_status(lead_id, "interested")
            st.success("Marked interested.")
    with col2:
        if st.button("Mark not interested", use_container_width=True):
            update_selected_status(lead_id, "not_interested")
            st.success("Marked not interested.")
        if st.button("Mark callback", use_container_width=True):
            update_selected_status(lead_id, "callback")
            st.success("Marked callback.")
    with col3:
        if st.button("Mark DNC", use_container_width=True):
            update_selected_status(lead_id, "dnc", "Manually marked DNC.")
            st.warning("Marked DNC.")
        if st.button("Mark busy", use_container_width=True):
            update_selected_status(lead_id, "busy")
            st.success("Marked busy.")
    with col4:
        if st.button("Save Transcript", use_container_width=True):
            save_current_transcript()
        if st.button("End Call", use_container_width=True):
            end_current_call()


def transcript_text():
    lines = []
    for item in st.session_state.conversation:
        speaker = item.get("role") or item.get("speaker", "Unknown")
        message = item.get("message") or item.get("text", "")
        timestamp = item.get("timestamp", "")
        prefix = f"[{timestamp}] " if timestamp else ""
        lines.append(f"{prefix}{speaker}: {message}")
    return "\n".join(lines)


def apply_ai_status(lead_id, call_id, status, summary):
    if status == "dnc":
        db.mark_dnc(lead_id)
    elif status in STATUSES:
        db.update_lead_status(lead_id, status)

    if call_id:
        db.update_call(call_id, status, transcript_text(), summary)


def detect_local_status(text):
    clean = text.lower()
    if any(phrase in clean for phrase in DNC_PHRASES):
        return {
            "reply": "Absolutely. I will make sure you are not called again. Thank you.",
            "status": "dnc",
            "summary": "Customer requested removal or no further calls.",
        }
    if any(phrase in clean for phrase in WRONG_NUMBER_PHRASES):
        return {
            "reply": "Sorry about that. I will mark this as a wrong number. Thank you.",
            "status": "wrong_number",
            "summary": "Customer said this is the wrong number.",
        }
    if any(phrase in clean for phrase in NOT_INTERESTED_PHRASES):
        return {
            "reply": "No problem. Thanks for your time, and have a good day.",
            "status": "not_interested",
            "summary": "Customer said they are not interested.",
        }
    return None


def active_lead_or_select():
    if st.session_state.active_lead_id:
        return db.get_lead(st.session_state.active_lead_id)

    leads = db.get_leads(include_dnc=True)
    lead_id = selected_lead_widget(leads, "live_lead_select")
    if lead_id:
        return db.get_lead(lead_id)
    return None


def speak_and_report(text, voice):
    result = tts_engine.speak_text(text, voice=voice)
    if result["ok"]:
        if result.get("message"):
            st.info(result["message"])
        else:
            st.success("Audio played.")
    else:
        st.error(result["message"])


def render_chat_transcript():
    if not st.session_state.conversation:
        st.info("Transcript is empty.")
        return

    for item in st.session_state.conversation:
        speaker = item.get("role") or item.get("speaker", "Unknown")
        message = item.get("message") or item.get("text", "")
        timestamp = item.get("timestamp", "")
        role = "assistant" if speaker == "AI" else "user"
        with st.chat_message(role):
            st.markdown(f"**{speaker}:** {message}")
            if timestamp:
                st.caption(timestamp)


def live_call_assistant_page(settings):
    st.header("Live Call Assistant")
    lead = active_lead_or_select()
    if not lead:
        return

    opening_script = render_opening_script(settings)

    st.subheader(f"{lead['name'] or 'Unknown'} - {lead['phone']}")
    st.caption(f"{lead['company'] or 'No company'} | Status: {lead['status']} | DNC: {'yes' if lead['dnc'] else 'no'}")

    with st.expander("Optional STT status", expanded=False):
        st.write(stt_engine.listen_from_microphone()["message"])

    confirmed = st.checkbox("I confirm this selected lead came from the uploaded CSV and is allowed to be called.", key="live_confirm")
    col_start, col_open, col_save, col_end = st.columns(4)
    with col_start:
        if st.button("Start Call", type="primary", use_container_width=True):
            start_call_for_lead(lead["id"], settings, confirmed)
    with col_open:
        if st.button("Speak Opening Script", use_container_width=True):
            add_message("AI", opening_script)
            speak_and_report(opening_script, settings["tts_voice"])
    with col_save:
        if st.button("Save Transcript", use_container_width=True):
            save_current_transcript()
    with col_end:
        if st.button("End Call", use_container_width=True):
            end_current_call()

    st.text_area("Opening script", opening_script, height=100, disabled=True)

    listen_col, manual_col = st.columns([1, 3])
    with listen_col:
        if st.button(f"Listen {settings['recording_seconds']} Seconds", use_container_width=True):
            with st.spinner(f"Listening for {settings['recording_seconds']} seconds..."):
                result = stt_engine.listen_from_microphone(
                    settings["recording_seconds"],
                    settings["selected_input_device"],
                )
            if result["ok"]:
                st.session_state.customer_said_input = result["text"]
                st.success("Recognized speech was placed into the text box.")
                st.rerun()
            else:
                st.error(result["message"])
    with manual_col:
        st.caption("Manual mode always works. Edit or replace the listened text before generating a reply.")

    customer_said = st.text_area(
        "Customer Said",
        height=120,
        placeholder="Type what the customer said...",
        key="customer_said_input",
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Generate Reply", use_container_width=True):
            if not customer_said.strip():
                st.warning("Type what the customer said first.")
            else:
                add_message("Customer", customer_said.strip())
                result = detect_local_status(customer_said)
                if result is None:
                    result = ai_agent.generate_reply(
                        transcript_text(),
                        lead,
                        opening_script,
                        settings["ai_behavior_instructions"],
                    )
                st.session_state.last_ai_reply = result["reply"]
                st.session_state.last_ai_status = result["status"]
                st.session_state.last_ai_summary = result["summary"]
                add_message("AI", result["reply"])
                apply_ai_status(lead["id"], st.session_state.active_call_id, result["status"], result["summary"])
                st.rerun()
    with col2:
        if st.button("Speak Reply", use_container_width=True):
            if st.session_state.last_ai_reply:
                speak_and_report(st.session_state.last_ai_reply, settings["tts_voice"])
            else:
                st.warning("Generate a reply first.")
    with col3:
        selected_status = st.selectbox("Classify Lead", STATUSES, index=STATUSES.index(st.session_state.last_ai_status) if st.session_state.last_ai_status in STATUSES else 6)
        if st.button("Save Classification", use_container_width=True):
            update_selected_status(lead["id"], selected_status)
            st.success(f"Saved status: {selected_status}")

    if st.session_state.last_ai_reply:
        st.info(f"AI reply: {st.session_state.last_ai_reply}")
        st.caption(f"Status: {st.session_state.last_ai_status} | Summary: {st.session_state.last_ai_summary}")

    st.subheader("Conversation Transcript")
    render_chat_transcript()
    st.text_area("Raw transcript", transcript_text(), height=220)


def call_history_page():
    st.header("Call History")
    calls = db.get_calls()
    if calls.empty:
        st.info("No calls yet.")
        return

    st.dataframe(calls, use_container_width=True)
    st.download_button(
        "Export call history as CSV",
        data=dataframe_csv(calls),
        file_name="call_history_export.csv",
        mime="text/csv",
    )

    call_options = {f"Call #{row.id} - {row.phone} - {row.status}": int(row.id) for row in calls.itertuples()}
    selected = st.selectbox("Review call", list(call_options.keys()))
    call = db.get_call(call_options[selected])
    st.text_area("Transcript", call["transcript"] or "", height=250)
    st.text_area("AI summary", call["ai_summary"] or "", height=100)


def audio_setup_page(settings):
    st.header("Audio Setup")
    st.write("Automatic listening is optional. Manual transcript input remains available if STT fails.")
    st.markdown(
        """
1. Install VB-Audio Virtual Cable from the official VB-Audio site.
2. In Chrome site settings for Google Voice, set the microphone to `CABLE Output`.
3. Set the AI TTS playback route to `CABLE Input` in Windows sound settings if you want the call to hear the AI voice.
4. Select your system microphone, headset, or call-audio capture device below for push-to-listen.
5. Keep Google Voice open and test with one permission-based lead only.
"""
    )
    st.info("Current TTS playback uses Windows audio routing. The selected output device is saved for setup tracking; route playback in Windows if needed.")

    result = stt_engine.list_audio_devices()
    if not result["ok"]:
        st.error(result["message"])
        return

    input_labels = device_labels(result["inputs"])
    output_labels = device_labels(result["outputs"])
    input_default = device_index_for_select(input_labels, settings["selected_input_device"])
    output_default = device_index_for_select(output_labels, settings["selected_output_device"])

    with st.form("audio_settings_form"):
        selected_input_label = st.selectbox("Recording input device", input_labels, index=input_default)
        selected_output_label = st.selectbox("TTS output device for setup tracking", output_labels, index=output_default)
        recording_seconds = st.number_input("Recording seconds", min_value=1, max_value=30, value=settings["recording_seconds"])
        tts_voice = st.text_input("TTS voice", value=settings["tts_voice"])
        submitted = st.form_submit_button("Save Audio Settings", type="primary")

    if submitted:
        save_audio_config(
            selected_device_from_label(selected_input_label),
            selected_device_from_label(selected_output_label),
            recording_seconds,
            tts_voice,
        )
        st.success("Audio settings saved to config.json.")

    st.subheader("Input Devices")
    st.dataframe(pd.DataFrame(result["inputs"]), use_container_width=True)
    st.subheader("Output Devices")
    st.dataframe(pd.DataFrame(result["outputs"]), use_container_width=True)


def call_quality_checklist_page(settings):
    st.header("Call Quality Checklist")
    config = screen_bot.load_config()

    st.checkbox("Google Voice is open in Chrome", key="check_google_voice_open")
    st.checkbox("VB-Audio Virtual Cable is installed", key="check_audio_cable")
    st.checkbox("Chrome / Google Voice microphone is set to CABLE Output", key="check_chrome_mic")

    coords_ready = all(config.get(key) for key in ["number_input", "call_button", "end_call_button"])
    st.write(f"Coordinates captured: {coords_ready}")
    st.write(f"Groq API key loaded: {bool(os.getenv('GROQ_API_KEY'))}")
    st.write(f"Selected input device: {config.get('selected_input_device')}")
    st.write(f"Selected output device: {config.get('selected_output_device')}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test TTS", use_container_width=True):
            speak_and_report("This is a test of the AI calling assistant voice.", settings["tts_voice"])
    with col2:
        if st.button("Test Listen", use_container_width=True):
            with st.spinner(f"Listening for {settings['recording_seconds']} seconds..."):
                result = stt_engine.listen_from_microphone(
                    settings["recording_seconds"],
                    settings["selected_input_device"],
                )
            if result["ok"]:
                st.success(result["text"])
            else:
                st.error(result["message"])


def settings_page(settings):
    st.header("Settings")
    st.write("Build the opening script and assistant behavior for this demo.")
    with st.form("settings_form"):
        business_name = st.text_input("Business name", value=settings["business_name"])
        offer = st.text_input("Offer/service", value=settings["offer"])
        opening_script = st.text_area("Opening script", value=settings["opening_script"], height=140)
        ai_behavior_instructions = st.text_area("AI behavior instructions", value=settings["ai_behavior_instructions"], height=120)
        tts_voice = st.text_input("TTS voice", value=settings["tts_voice"])
        call_delay_seconds = st.number_input("Call delay between numbers, seconds", min_value=5, max_value=3600, value=settings["call_delay_seconds"])
        daily_call_limit = st.number_input("Daily call limit", min_value=1, max_value=500, value=settings["daily_call_limit"])
        submitted = st.form_submit_button("Save Settings", type="primary")

    if submitted:
        save_settings(
            {
                "business_name": business_name,
                "offer": offer,
                "opening_script": opening_script,
                "ai_behavior_instructions": ai_behavior_instructions,
                "tts_voice": tts_voice,
                "call_delay_seconds": int(call_delay_seconds),
                "daily_call_limit": int(daily_call_limit),
            }
        )
        config = screen_bot.load_config()
        config["tts_voice"] = tts_voice
        screen_bot.save_config(config)
        st.success("Settings saved.")

    st.subheader("Environment")
    st.write("GROQ_API_KEY loaded:", bool(os.getenv("GROQ_API_KEY")))


def main():
    st.set_page_config(page_title="AI Calling Assistant", layout="wide")
    apply_dark_theme()
    init_state()
    settings = load_settings()

    system_check_sidebar()

    page = st.sidebar.radio(
        "Sections",
        [
            "Dashboard",
            "Leads CRM",
            "Lead Detail",
            "Setup Coordinates",
            "Audio Setup",
            "Campaign Control",
            "Live Call Assistant",
            "Call History",
            "Call Quality Checklist",
            "Settings",
        ],
    )

    if page == "Dashboard":
        dashboard_page(settings)
    elif page == "Leads CRM":
        portfolio_header("Leads CRM", "Search, filter, classify, and export imported leads.")
        warning_banner()
        crm_leads_page()
    elif page == "Lead Detail":
        portfolio_header("Lead Detail", "Review one lead at a time and start only a confirmed manual call.")
        warning_banner()
        lead_detail_page(settings)
    elif page == "Setup Coordinates":
        portfolio_header("Setup Coordinates", "Capture Google Voice screen targets for local browser automation.")
        warning_banner()
        setup_coordinates_page()
    elif page == "Audio Setup":
        portfolio_header("Audio Setup", "Configure optional push-to-listen audio devices while keeping manual mode available.")
        warning_banner()
        audio_setup_page(settings)
    elif page == "Campaign Control":
        portfolio_header("Campaign Control", "Manual one-call-at-a-time controls with confirmation and delay safeguards.")
        warning_banner()
        campaign_control_page(settings)
    elif page == "Live Call Assistant":
        portfolio_header("Live Call Assistant", "Guide a single active call with TTS, optional listening, and transcript capture.")
        warning_banner()
        live_call_assistant_page(settings)
    elif page == "Call History":
        portfolio_header("Call History", "Review transcripts, statuses, summaries, and export the call log.")
        warning_banner()
        call_history_page()
    elif page == "Call Quality Checklist":
        portfolio_header("Call Quality Checklist", "Preflight checks before a permission-based demo call.")
        warning_banner()
        call_quality_checklist_page(settings)
    elif page == "Settings":
        portfolio_header("Settings", "Edit business script, assistant behavior, safety limits, and voice.")
        warning_banner()
        settings_page(settings)


if __name__ == "__main__":
    main()
