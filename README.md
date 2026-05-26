# AI Google Voice Calling Assistant

Portfolio-ready local Windows desktop prototype for a one-call-at-a-time AI calling workflow. The app combines Streamlit, SQLite, Groq, Edge TTS, PyAutoGUI, and optional push-to-listen audio capture to demonstrate how a human-supervised sales assistant could manage leads, generate short replies, speak responses, and save call history.

This is a personal demo/testing project only. It is not a robocaller, spam dialer, or mass outbound system.

## Safety First

- Manual start is required before every call.
- The app only dials a selected lead imported from CSV.
- No automatic full-list calling is implemented.
- A confirmation checkbox is required before dialing.
- A five-second countdown runs before PyAutoGUI clicks Google Voice.
- Daily call limit and delay between calls are enforced.
- DNC/remove phrases are detected and saved immediately.
- Google Voice browser automation may violate the Google Voice Acceptable Use Policy.

## Features

- Professional dark Streamlit dashboard
- CRM-style lead table with search and status filters
- Lead detail page with one-lead actions
- Campaign control for one selected lead at a time
- Live call assistant with manual transcript input
- Optional push-to-listen mode using `sounddevice`
- Groq JSON reply generation with robust fallback handling
- Edge TTS speaking with Windows playback fallback
- SQLite lead, settings, and call history storage
- Call analytics cards for total leads, calls, interested, callback, DNC, completed, daily limit, and delay
- CSV export for leads and call history
- Coordinate capture for Google Voice number input, call button, and end button

## Screenshots

Place screenshots in the [screenshots](screenshots) folder before publishing.

Suggested screenshots:

- Dashboard analytics: `screenshots/dashboard.png`
- Leads CRM: `screenshots/leads-crm.png`
- Lead detail: `screenshots/lead-detail.png`
- Live call assistant: `screenshots/live-call-assistant.png`
- Audio setup: `screenshots/audio-setup.png`

Do not include real phone numbers, private transcripts, or API keys in screenshots.

## Tech Stack

- Python 3.12
- Streamlit
- SQLite
- pandas
- Groq Python SDK
- edge-tts
- playsound
- PyAutoGUI
- pyperclip
- sounddevice, soundfile, numpy
- SpeechRecognition

## Windows Setup

Use Python 3.12. Python 3.14 may cause package install issues on Windows.

```powershell
cd F:\Projects\ai-google-voice-agent
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python --version
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m streamlit run app.py
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

## CSV Format

Upload leads with these columns:

```csv
name,phone,company,email,notes
Jane Demo,+15551234567,Demo Co,jane@example.com,Sample permission-based test lead
```

The included [leads.csv](leads.csv) uses sample demo data only.

## First Run

1. Start the app with `python -m streamlit run app.py`.
2. Open **Leads CRM** and import `leads.csv`.
3. Open Google Voice manually in Chrome.
4. Open **Setup Coordinates** and capture:
   - Number input
   - Call button
   - End call button
5. Open **Settings** and edit business name, offer, opening script, AI behavior, voice, call delay, and daily limit.
6. Open **Call Quality Checklist** and run preflight checks.
7. Open **Lead Detail**, choose one lead, check the confirmation box, and start one call.
8. Use **Live Call Assistant** to speak, listen or type, generate replies, classify, save transcript, and end the call.

## Phase 3 Audio Setup

Push-to-listen is optional. Manual text input remains the dependable fallback.

1. Install VB-Audio Virtual Cable from the official VB-Audio website.
2. Restart Windows if requested.
3. Confirm Windows shows `CABLE Input` and `CABLE Output`.
4. In Chrome site settings for Google Voice, set microphone to `CABLE Output` if you are routing AI audio into the call.
5. In Windows sound settings, route app playback to `CABLE Input` if needed.
6. Open **Audio Setup** and choose the input device for listening.
7. Open **Call Quality Checklist** and test TTS and listen mode.

Note: the selected output device is saved in `config.json` for setup tracking, but `playsound` follows Windows audio routing.

## Troubleshooting

`streamlit` is not recognized:

```powershell
python -m streamlit run app.py
```

`pygame` missing:

This project no longer uses `pygame`.

`pyaudio` build error:

This project does not use `pyaudio`.

`sounddevice` cannot find devices:

- Confirm Windows sees your microphone or virtual cable.
- Close apps that may have exclusive device control.
- Try the `Default` input device in **Audio Setup**.
- Reinstall with `pip install sounddevice soundfile numpy`.

Groq key missing:

Create `.env` from `.env.example` and add your `GROQ_API_KEY`.

## Project Structure

```text
ai-google-voice-agent/
  app.py
  screen_bot.py
  ai_agent.py
  tts_engine.py
  stt_engine.py
  database.py
  config.json
  leads.csv
  requirements.txt
  .env.example
  .gitignore
  .streamlit/
    config.toml
  screenshots/
    README.md
```

## Portfolio Description

A local, safety-constrained AI call assistant prototype demonstrating CRM lead handling, human-supervised dialing, AI-generated call responses, TTS playback, optional push-to-listen transcription, and SQLite call history. Built to show practical orchestration of desktop automation, LLM APIs, audio tooling, and a polished Streamlit dashboard without enabling mass calling.
