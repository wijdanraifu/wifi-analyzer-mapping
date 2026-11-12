"""
ai_advisor.py - WiFi-Radar ID (Orang 4: AI Advisor)

Kontrak output (dipakai database.save_scan_result & app.py):
    {'summary': str, 'suitable_for': list[str], 'source': 'ai' | 'rule'}

Alur:
    get_suitable_activities()  -> aturan deterministik aktivitas yang cocok
    build_rule_based_summary() -> ringkasan tanpa AI (fallback, selalu tersedia)
    generate_ai_summary()      -> ringkasan via Gemini API (jika API key tersedia)
    generate_advice()          -> fungsi utama yang dipanggil app.py

API key dibaca dari `.streamlit/secrets.toml` (GEMINI_API_KEY) atau
environment variable GEMINI_API_KEY. Tanpa key, otomatis memakai fallback.
"""

import os

try:
    import requests
except ImportError:
    requests = None

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 20  # detik

ACTIVITIES = ["Rapat Online", "Coding/Kerja", "Streaming 4K", "Transaksi Perbankan"]


# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
def _get_secret(name, default=None):
    """Ambil secret dari st.secrets, lalu environment variable."""
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # tidak ada secrets.toml / tidak berjalan di Streamlit
        pass
    return os.environ.get(name, default)


def is_ai_configured():
    return bool(_get_secret("GEMINI_API_KEY")) and requests is not None


# ---------------------------------------------------------------------------
# Aturan deterministik
# ---------------------------------------------------------------------------
def get_suitable_activities(network_data, security_data):
    """Tentukan aktivitas yang cocok berdasarkan QoS + skor keamanan."""
    dl = float(network_data.get("download_mbps", 0))
    ul = float(network_data.get("upload_mbps", 0))
    ping = float(network_data.get("ping_ms", 999))
    jitter = float(network_data.get("jitter_ms", 999))
    video = float(network_data.get("video_mbps", dl))
    category = security_data.get("category", "Rawan")

    suitable = []
    if dl >= 5 and ul >= 3 and ping <= 100 and jitter <= 30:
        suitable.append("Rapat Online")
    if dl >= 5 and ping <= 150:
        suitable.append("Coding/Kerja")
    if video >= 25 and not network_data.get("is_throttled", False):
        suitable.append("Streaming 4K")
    if category == "Aman":
        suitable.append("Transaksi Perbankan")

    # Jaringan berbahaya: jangan rekomendasikan aktivitas yang butuh login
    if category == "Bahaya":
        suitable = [a for a in suitable if a == "Streaming 4K"]
    return suitable


def build_rule_based_summary(network_data, security_data, location_name=None):
    """Ringkasan dalam Bahasa Indonesia tanpa AI."""
    place = f"Wi-Fi di {location_name}" if location_name else "Jaringan ini"
    dl = float(network_data.get("download_mbps", 0))
    ping = float(network_data.get("ping_ms", 0))
    category = security_data.get("category", "Rawan")

    if dl >= 50 and ping <= 20:
        speed = f"{place} sangat cepat dan responsif ({dl:.1f} Mbps, ping {ping:.0f} ms)."
    elif dl >= 15 and ping <= 60:
        speed = f"{place} cukup lancar untuk aktivitas harian ({dl:.1f} Mbps, ping {ping:.0f} ms)."
    else:
        speed = f"{place} tergolong lambat ({dl:.1f} Mbps, ping {ping:.0f} ms); cocok untuk browsing ringan saja."

    if network_data.get("is_throttled"):
        throttle = (f" Terdeteksi indikasi pembatasan trafik streaming "
                    f"(estimasi {float(network_data.get('video_mbps', 0)):.1f} Mbps).")
    else:
        throttle = " Tidak ada indikasi pembatasan trafik streaming."

    if category == "Aman":
        security = " Konfigurasi keamanan baik sehingga relatif aman untuk transaksi sensitif."
    elif category == "Rawan":
        security = (" Peringatan keamanan: hindari membuka Mobile Banking tanpa VPN atau "
                    "aktifkan Private DNS (mis. 1.1.1.1) di perangkat Anda.")
    else:
        security = (" BAHAYA: jangan memasukkan password atau membuka layanan finansial; "
                    "gunakan VPN atau data seluler.")
    return speed + throttle + security


# ---------------------------------------------------------------------------
# Gemini API
# ---------------------------------------------------------------------------
def generate_ai_summary(network_data, security_data, location_name=None):
    """Minta ringkasan ke Gemini. Raise exception jika gagal."""
    api_key = _get_secret("GEMINI_API_KEY")
    if not api_key or requests is None:
        raise RuntimeError("Gemini API key belum dikonfigurasi.")
    model = _get_secret("GEMINI_MODEL", DEFAULT_MODEL)

    findings = "; ".join(security_data.get("findings", []))
    prompt = (
        "Kamu adalah penasihat keamanan dan kualitas Wi-Fi publik untuk mahasiswa di Indonesia. "
        "Tulis ringkasan 2-3 kalimat dalam Bahasa Indonesia yang jelas dan praktis, "
        "tanpa markdown, berdasarkan data berikut.\n"
        f"Lokasi: {location_name or 'tidak disebutkan'}\n"
        f"Download: {network_data.get('download_mbps')} Mbps, Upload: {network_data.get('upload_mbps')} Mbps, "
        f"Ping: {network_data.get('ping_ms')} ms, Jitter: {network_data.get('jitter_ms')} ms\n"
        f"Indikasi throttling streaming: {'ya' if network_data.get('is_throttled') else 'tidak'} "
        f"(estimasi streaming {network_data.get('video_mbps')} Mbps)\n"
        f"Skor keamanan: {security_data.get('score')}/100 ({security_data.get('category')})\n"
        f"Temuan keamanan: {findings}\n"
        "Sebutkan aktivitas yang cocok dan saran keamanan konkret."
    )
    resp = requests.post(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("Respons Gemini kosong.")
    return text


# ---------------------------------------------------------------------------
# Fungsi utama untuk app.py
# ---------------------------------------------------------------------------
def generate_advice(network_data, security_data, location_name=None, use_ai=True):
    """Hasilkan rekomendasi sesuai kontrak data. Selalu berhasil (fallback rule-based)."""
    suitable = get_suitable_activities(network_data, security_data)
    if use_ai and is_ai_configured():
        try:
            summary = generate_ai_summary(network_data, security_data, location_name)
            return {"summary": summary, "suitable_for": suitable, "source": "ai"}
        except Exception:
            pass  # jatuh ke fallback di bawah
    return {
        "summary": build_rule_based_summary(network_data, security_data, location_name),
        "suitable_for": suitable,
        "source": "rule",
    }


if __name__ == "__main__":
    sample_net = {"download_mbps": 48.5, "upload_mbps": 32.1, "ping_ms": 14.0,
                  "jitter_ms": 3.0, "is_throttled": True, "video_mbps": 4.2}
    sample_sec = {"score": 62, "category": "Rawan",
                  "findings": ["Header HSTS tidak ada. (-10)"]}
    print(generate_advice(sample_net, sample_sec, "Kopi Lembah UGM"))
