# WiFi-Radar ID 📡

**Public Wi-Fi Intelligence** – a Streamlit dashboard that measures the quality (speed, ping, jitter, throttling) and security (encryption, DNS, SSL/TLS, captive portal) of public Wi-Fi, gives AI recommendations, and shares the results on a community map.

Project Prokom Kelompok 7.

## Features

- **Overview**: run a live network test (or a simulation for demos). You get a network-health score, QoS metrics, a net-neutrality check, a security audit, and AI Advisor recommendations.
- **Community Map**: an interactive map with color-coded pins (green = Aman, yellow = Rawan, red = Bahaya), a speed vs. security chart, and per-location details.
- **Scan History**: a table of past scans with filters and CSV export.

## Project structure

```
app.py                     # Streamlit UI (entry point)
modules/
  database.py              # SQLite: schema, seed data, save/read scan results  (Orang 1)
  network_scanner.py       # Speedtest, ping, jitter, throttling check           (Orang 2)
  security_test.py         # Wi-Fi encryption, DNS, SSL/TLS, headers, portal     (Orang 3)
  ai_advisor.py            # Gemini summary + rule-based fallback                (Orang 4)
  visualizer.py            # UI components, map, charts, tables                  (Orang 5)
data/seed_data.json        # Initial location and security-rule data
.streamlit/config.toml     # Dark theme
.streamlit/secrets.toml.example
```

### Data contracts between modules

| Module | Output |
|---|---|
| `network_scanner.run_network_scan()` | `{download_mbps, upload_mbps, ping_ms, jitter_ms, is_throttled, video_mbps, quality_score, ssid, signal, ...}` |
| `security_test.audit_wifi()` | `{score: 0-100, category: Aman/Rawan/Bahaya, findings: list[str]}` |
| `ai_advisor.generate_advice()` | `{summary: str, suitable_for: list[str], source: ai/rule}` |
| `database.save_scan_result()` | Saves all three outputs above to `wifi_scan_logs` |

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

The database `data/wifi_radar.db` is created automatically on first run and filled from `data/seed_data.json`.

### AI Advisor (optional)

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in `GEMINI_API_KEY`. Without a key, the AI Advisor uses its rule-based mode automatically.

## Notes

- Reading the SSID, signal strength, and encryption type uses `netsh` and **only works on Windows**. On other operating systems and in the cloud, the speed and security tests still run.
- Speedtest is often blocked on cloud hosting (e.g. Streamlit Community Cloud). Use **Simulation** mode for demos there.
- `video_mbps` (streaming throughput) is an **estimate** based on comparing latency between streaming services and general services, not a direct measurement.
- Testing each module on its own: `python -m modules.database`, `python -m modules.security_test`, `python -m modules.network_scanner`, `python -m modules.ai_advisor`.
