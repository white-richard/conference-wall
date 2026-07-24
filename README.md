# Conference Wall

`confwall` is a lightweight Python CLI application and digital signage slideshow that displays upcoming software-systems, HCI, and machine-learning conference submission deadlines as a full-screen browser slideshow.

![confwall preview](assets/fallback-city.jpg)

---

## Key Features

- **Full-screen City Signage**: Displays a high-resolution background photograph for each conference city.
- **Strict 4-Month Calendar Window**: Shows paper submission deadlines occurring from the current time through exactly four calendar months in the future.
- **Topic Allowlisting**: Explicitly configures primary focus areas (_Software Systems_, _HCI_, _Machine Learning_) per venue via `config.yml`.
- **CCF-Deadlines Integration**: Downloads snapshot repositories in a single request and parses full-paper deadlines (abstract-only deadlines are ignored).
- **Timezone Awareness**: Normalizes deadlines to UTC for sorting and filtering while retaining original display timezones (e.g. AoE, UTC-8, UTC+5:30).
- **Photo Overrides & Caching**: Supports Pexels API search, persistent manifest caching (`data/photo_manifest.json`), and manual photo overrides (`photo_overrides.yml`).
- **Resilient Atomic Updates**: Atomic directory replacement ensures that an update failure preserves the last working slideshow without down-time.

---

## 1. Installation

### Using `uv`

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate

uv pip install -e ".[dev]"
```

### Standard Python `venv`

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## 2. Obtaining a Pexels API Key

1. Sign up for a free account at [Pexels API](https://www.pexels.com/api/).
2. Request an API key from your Pexels dashboard.
3. Export your key in your shell environment:

```bash
export PEXELS_API_KEY="your_pexels_api_key_here"
```

---

## 3. Creating `config.yml`

Copy the provided example file to `config.yml`:

```bash
cp config.example.yml config.yml
```

Example configuration structure:

```yaml
window_months: 4
slide_seconds: 15
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
3. On dedicated display hardware (e.g. Raspberry Pi connected to a TV), launch Chrome or Chromium in kiosk mode:

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

### Editing the Venue Allowlist

Modify `config.yml` to add or remove venue IDs and set their `primary_focus` (_Software Systems_, _HCI_, _Machine Learning_).

### Pinning or Replacing a City Photo

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

## 8. Deployment as a Systemd Service

### `confwall.service` (`/etc/systemd/system/confwall.service`)

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
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### `confwall-refresh.service` (`/etc/systemd/system/confwall-refresh.service`)

```ini
[Unit]
Description=Confwall Deadline Refresh Job

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/confwall
Environment="PEXELS_API_KEY=your_key_here"
ExecStart=/home/pi/confwall/.venv/bin/confwall refresh
```

### `confwall-refresh.timer` (`/etc/systemd/system/confwall-refresh.timer`)

```ini
[Unit]
Description=Run Confwall Refresh twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now confwall.service
sudo systemctl enable --now confwall-refresh.timer
```

---

## 9. Attribution and License

- **Conference Data**: Sourced from [CCF-Deadlines](https://github.com/ccfddl/ccf-deadlines).
- **Photography**: Photos provided via [Pexels API](https://www.pexels.com). Photographer credit is displayed on each slide.
- **License**: MIT License.
