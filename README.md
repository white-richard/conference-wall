# confwall 🌆

`confwall` is a lightweight, cross-platform Python 3.12 CLI application and digital signage slideshow that displays upcoming software-systems, HCI, and machine-learning conference submission deadlines as a full-screen browser slideshow.

![confwall preview](assets/fallback-city.jpg)

---

## Key Features

- **Full-screen City Signage**: Displays a high-resolution background photograph for each conference city.
- **Strict 4-Month Calendar Window**: Shows paper submission deadlines occurring from the current time through exactly four calendar months in the future.
- **Zero-Manual-Labeling Auto-Discovery**: Automatically discovers and classifies conferences across *Software Systems*, *HCI*, and *Machine Learning* based on upstream category metadata.
- **Cross-Platform Compatibility**: Fully compatible with macOS, Windows (PowerShell/CMD), and Linux.
- **Timezone & PST Conversion**: Automatically converts all deadline display times to Pacific Time (PST/PDT) while retaining original source timezone notes.
- **Photo Overrides & Caching**: Supports Pexels API search, persistent manifest caching (`data/photo_manifest.json`), and manual photo overrides (`photo_overrides.yml`).
- **Resilient Atomic Updates**: Atomic directory replacement ensures that an update failure preserves the last working slideshow without down-time.

---

## 1. Installation

### Using `uv` (Recommended)

**macOS / Linux**:
```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Windows (PowerShell)**:
```powershell
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
```

### Standard Python `venv`

**macOS / Linux**:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows (CMD / PowerShell)**:
```cmd
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

---

## 2. Obtaining a Pexels API Key

1. Sign up for a free account at [Pexels API](https://www.pexels.com/api/).
2. Request an API key from your Pexels dashboard.
3. Export your key in your shell environment:

**macOS / Linux**:
```bash
export PEXELS_API_KEY="your_pexels_api_key_here"
```

**Windows (PowerShell)**:
```powershell
$env:PEXELS_API_KEY="your_pexels_api_key_here"
```

**Windows (CMD)**:
```cmd
set PEXELS_API_KEY="your_pexels_api_key_here"
```

*Note: The API key is read exclusively from `PEXELS_API_KEY` and is never written to configuration, logs, or generated static assets.*

---

## 3. Creating `config.yml`

Copy the provided example file to `config.yml`:

**macOS / Linux**:
```bash
cp config.example.yml config.yml
```

**Windows**:
```cmd
copy config.example.yml config.yml
```

Example configuration structure:

```yaml
window_months: 4
slide_seconds: 15
display_timezone: PST
auto_discover: true
venues:
  osdi:
    aliases: [OSDI]
    primary_focus: Software Systems
  chi:
    aliases: [CHI]
    primary_focus: HCI
  neurips:
    aliases: [NeurIPS, NIPS]
    primary_focus: Machine Learning
```

---

## 4. Running the Application

To perform a refresh and serve the static slideshow over HTTP on port 8000:

```bash
confwall run --host 0.0.0.0 --port 8000
```

To refresh data without running the HTTP server:

```bash
confwall refresh
```

To serve an existing static site build:

```bash
confwall serve --directory build --host 127.0.0.1 --port 8000
```

---

## 5. Viewing in Browser & Kiosk Mode

1. Open `http://127.0.0.1:8000` in your web browser.
2. Press **`f`** on your keyboard to enter fullscreen mode.
3. On dedicated display hardware (e.g. Raspberry Pi or Windows Kiosk display), launch Chrome or Edge in kiosk mode:

**Windows (Command Prompt / PowerShell)**:
```cmd
start msedge --kiosk http://127.0.0.1:8000 --edge-kiosk-type=fullscreen
```

**Linux / macOS**:
```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars http://127.0.0.1:8000
```

### Keyboard Shortcuts

- **`Right Arrow` / `Click`**: Advance to next slide.
- **`Left Arrow`**: Return to previous slide.
- **`Space`**: Pause / resume slideshow.
- **`f`**: Toggle fullscreen mode.

---

## 6. Customization & Photo Overrides

Create `photo_overrides.yml` to pin a specific Pexels photo ID or use a local image file:

```yaml
photos:
  "las vegas|usa":
    pexels_id: 12345678
  "hamburg|germany":
    file: local_photos/hamburg.jpg
    credit: "Photo by Lab Member"
```

---

## 7. Running Tests

Run unit, integration, and Playwright browser tests:

```bash
# Run linter
uv run ruff check .

# Run test suite with coverage report
uv run pytest -m "not live" --cov=confwall --cov-report=term-missing

# Run optional live integration tests (requires network)
uv run pytest -m live
```

---

## 8. Deployment Options

### Windows Task Scheduler (Windows Service / Refresh)

You can run `confwall refresh` automatically twice a day using Windows Task Scheduler:

```powershell
schtasks /Create /TN "ConfwallRefresh" /TR "C:\path\to\confwall\.venv\Scripts\confwall.exe refresh" /SC DAILY /ST 00:00 /RI 720 /DU 24:00
```

### Linux Systemd Service

See systemd unit samples for Linux background deployment:

```ini
[Unit]
Description=Confwall Slideshow HTTP Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/confwall
ExecStart=/home/pi/confwall/.venv/bin/confwall serve --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 9. Attribution and License

- **Conference Data**: Sourced from [CCF-Deadlines](https://github.com/ccfddl/ccf-deadlines).
- **Photography**: Photos provided via [Pexels API](https://www.pexels.com). Photographer credit is displayed on each slide.
- **License**: MIT License.
