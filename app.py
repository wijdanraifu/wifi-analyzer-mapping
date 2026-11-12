from __future__ import annotations

from html import escape

import streamlit as st

from modules import ai_advisor, network_scanner, security_test
from modules.database import (
    find_location_by_name,
    generate_location_id,
    get_all_locations_summary,
    get_scan_history,
    init_db,
    save_scan_result,
)
from modules.visualizer import (
    CATEGORY_TONE,
    render_activity_chips,
    render_community_map,
    render_history_table,
    render_metric_card,
    render_section_heading,
    render_speed_gauge,
    render_speed_security_chart,
    render_status_card,
)

st.set_page_config(
    page_title="WiFi-Radar ID | Public Wi-Fi Intelligence",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Theme ----------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --bg:#080f1c; --panel:#142238; --panel2:#1a2b42; --line:#344a65; --muted:#b8c7d9; --text:#f4f8ff; --cyan:#35d5e8; --blue:#638cff; }
    html, body, [data-testid="stAppViewContainer"] { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; }
    [data-testid="stHeader"] { background:rgba(8,15,28,.92); }
    [data-testid="stSidebar"] { background:#0b1626; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] * { color:var(--text); }
    .block-container { padding-top:2rem; padding-bottom:3rem; max-width:1440px; }
    h1,h2,h3,.brand-name,.section-title { font-family:'Space Grotesk',sans-serif !important; }
    .brand { display:flex; align-items:center; gap:11px; padding:8px 4px 24px; }
    .brand-mark { width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#35d5e8,#638cff);display:flex;align-items:center;justify-content:center;color:#06111e;font-size:20px;font-weight:700; }
    .brand-name { font-size:19px;font-weight:700;letter-spacing:-.5px; }
    .brand-sub { color:var(--muted);font-size:10px;letter-spacing:1.6px;text-transform:uppercase;margin-top:2px; }
    .eyebrow { color:var(--cyan);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px; }
    .page-title { font-family:'Space Grotesk',sans-serif;font-size:32px;font-weight:700;letter-spacing:-1px;color:var(--text);margin:0; }
    .page-desc { color:var(--muted);font-size:14px;margin-top:6px; }
    .topline { border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px; }
    .panel { background:linear-gradient(145deg,#122238,#0e1929);border:1px solid var(--line);border-radius:18px;padding:22px 24px; }
    .panel-label { color:var(--muted);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase; }
    .gauge-wrap { display:flex;flex-direction:column;align-items:center;justify-content:center;padding:14px 0 2px; }
    .gauge { width:218px;height:218px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(from 225deg,var(--cyan) 0 var(--progress),#26364c var(--progress) 75%,transparent 75% 100%);position:relative; }
    .gauge:before { content:'';position:absolute;inset:10px;border-radius:50%;background:#101d30;border:1px solid #263a52; }
    .gauge-inner { position:relative;text-align:center; }
    .gauge-label { color:#9db3ca;font-size:10px;letter-spacing:1.7px;font-weight:700; }
    .gauge-value { font-family:'Space Grotesk',sans-serif;font-size:49px;font-weight:700;line-height:1.15;color:#f2f8ff;margin-top:8px; }
    .gauge-value span { font-family:'DM Sans',sans-serif;font-size:12px;color:#9db3ca;font-weight:500; }
    .gauge-unit { color:var(--cyan);font-size:10px;letter-spacing:1.4px;margin-top:5px; }
    .gauge-subtext { color:var(--muted);font-size:11px;margin-top:14px; }
    .metric-card { background:#111f32;border:1px solid var(--line);border-radius:15px;padding:17px 18px;min-height:136px; }
    .metric-top { display:flex;align-items:center;justify-content:space-between;margin-bottom:14px; }
    .metric-icon { width:30px;height:30px;display:grid;place-items:center;border-radius:9px;background:#1a3448;color:var(--cyan);font-size:15px; }
    .metric-note { font-size:10px;color:#b8c7d9; }
    .metric-title { color:#a9bbce;font-size:12px; }
    .metric-value { color:#f2f7ff;font-family:'Space Grotesk',sans-serif;font-size:27px;font-weight:700;margin-top:4px; }
    .metric-value span { font-family:'DM Sans',sans-serif;font-size:12px;color:#91a6bd;font-weight:500; }
    .section-heading { margin:26px 0 14px; }
    .section-title { font-size:18px;font-weight:600;color:var(--text); }
    .section-subtitle { color:var(--muted);font-size:12px;margin-top:3px; }
    .status-card { display:flex;gap:12px;align-items:flex-start;background:#111f32;border:1px solid var(--line);border-radius:14px;padding:16px;min-height:112px; }
    .status-dot { width:9px;height:9px;border-radius:50%;background:#8295aa;margin-top:5px;flex-shrink:0; }
    .status-card.good .status-dot { background:#39d6a2;box-shadow:0 0 12px #39d6a255; }
    .status-card.warning .status-dot { background:#f5b84b;box-shadow:0 0 12px #f5b84b55; }
    .status-card.danger .status-dot { background:#f05a5a;box-shadow:0 0 12px #f05a5a55; }
    .chip-row { display:flex;flex-wrap:wrap;gap:8px;margin-top:6px; }
    .chip { background:#16314a;border:1px solid #1d5264;color:#b9f0f7;border-radius:999px;padding:5px 12px;font-size:12px;font-weight:600; }
    .chip-empty { display:inline-block;background:#3a1c24;border-color:#7a2e3a;color:#ffc4c4; }
    .legend { display:flex;gap:18px;margin-top:10px;color:var(--muted);font-size:12px; }
    .legend-item { display:flex;align-items:center;gap:6px; }
    .legend-dot { width:10px;height:10px;border-radius:50%;display:inline-block; }
    .status-title { color:#9db1c7;font-size:11px; }
    .status-value { color:#f0f6ff;font-size:14px;font-weight:700;margin-top:4px; }
    .status-detail { color:#b8c7d9;font-size:11px;margin-top:4px;line-height:1.45; }
    .info-banner { background:#10283a;border:1px solid #1d5264;border-radius:12px;padding:13px 16px;color:#b9dce7;font-size:12px;line-height:1.5; }
    div.stButton > button { background:linear-gradient(100deg,#35d5e8,#638cff);color:#06111e;border:0;border-radius:11px;font-weight:700;padding:.65rem 1rem;min-height:44px; }
    div.stButton > button:hover { border:0;color:#06111e;filter:brightness(1.08); }
    /* Input location, SSID, and selectbox */
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    background: #1A2B42 !important;
    color: #F4F8FF !important;
    border: 1px solid #526B8A !important;
    border-radius: 10px;
}

/* Placeholder text */
div[data-testid="stTextInput"] input::placeholder {
    color: #B8C7D9 !important;
    opacity: 1;
}

/* Input labels */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label {
    color: #D5E1EF !important;
    font-weight: 600;
}
    [data-testid="stMetric"] { background:#111f32;padding:14px;border:1px solid var(--line);border-radius:12px; }
    [data-testid="stMetricLabel"] { color:#9db1c7; }
    [data-testid="stMetricValue"] { color:#f2f7ff; }
    hr { border-color:var(--line); }
    .footer { color:#71869d;font-size:10px;text-align:center;margin-top:36px;padding-top:16px;border-top:1px solid var(--line); }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Database bootstrap ----------
@st.cache_resource(show_spinner=False)
def bootstrap_database() -> bool:
    """Buat tabel + muat seed_data.json sekali per proses Streamlit."""
    init_db()
    return True


bootstrap_database()

# Skenario simulasi jaringan -> skenario keamanan yang dipasangkan
SIMULATION_PAIRS = {
    "Cepat & aman": ("cepat", "aman"),
    "Sedang & rawan": ("sedang", "rawan"),
    "Lambat & berbahaya": ("lambat", "bahaya"),
}
NEW_LOCATION = "➕ Lokasi baru"
DEFAULT_LAT, DEFAULT_LON = -7.76951, 110.37825  # Perpustakaan Pusat UGM


def run_full_check(location: dict, ssid: str, simulate: tuple | None, save: bool) -> None:
    """Jalankan scanner -> audit keamanan -> AI advisor -> simpan ke database."""
    net_sim, sec_sim = simulate if simulate else (None, None)
    with st.status("Menjalankan pengujian jaringan...", expanded=True) as status:
        try:
            st.write("1/4 · Mengukur kecepatan, ping, jitter, dan indikasi throttling...")
            network_data = network_scanner.run_network_scan(simulate=net_sim)

            st.write("2/4 · Mengaudit keamanan Wi-Fi (enkripsi, DNS, SSL/TLS, captive portal)...")
            security_data = security_test.audit_wifi(simulate=sec_sim, wifi_info=network_data)

            st.write("3/4 · Menyusun rekomendasi AI Advisor...")
            ai_data = ai_advisor.generate_advice(network_data, security_data, location["name"])

            scan_id = None
            if save:
                st.write("4/4 · Menyimpan hasil ke database komunitas...")
                detected_ssid = network_data.get("ssid")
                if not ssid and detected_ssid not in (None, "", "Tidak terhubung", "Simulasi"):
                    ssid = detected_ssid
                new_info = None
                if location["is_new"]:
                    new_info = {
                        "name": location["name"],
                        "area": location["area"] or "Yogyakarta",
                        "ssid": ssid or "Public_WiFi",
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                    }
                scan_id = save_scan_result(location["location_id"], network_data,
                                           security_data, ai_data, new_info)
            else:
                st.write("4/4 · Hasil simulasi tidak disimpan ke database.")
        except (RuntimeError, ValueError) as exc:
            status.update(label="Pengujian gagal", state="error")
            st.error(str(exc))
            return

        status.update(label="Pengujian selesai", state="complete", expanded=False)

    st.session_state["last_result"] = {
        "location": location["name"],
        "network": network_data,
        "security": security_data,
        "ai": ai_data,
        "scan_id": scan_id,
    }
    st.rerun()


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-mark">⌁</div><div><div class="brand-name">WiFi-Radar ID</div><div class="brand-sub">Public Wi-Fi Intelligence</div></div></div>',
        unsafe_allow_html=True,
    )
    page = st.radio(
        "NAVIGATION",
        ["Overview", "Community Map", "Scan History"],
        label_visibility="visible",
    )
    st.markdown("---")
    st.markdown("<div class='panel-label'>SYSTEM STATUS</div>", unsafe_allow_html=True)
    st.caption("● Database terhubung")
    st.caption("● Scanner siap" if network_scanner.sp else "○ speedtest-cli belum terpasang (hanya simulasi)")
    st.caption("● AI Advisor: Gemini" if ai_advisor.is_ai_configured() else "○ AI Advisor: mode aturan (tanpa API key)")
    st.markdown("---")
    st.caption("WiFi-Radar ID · Project Prototype")

if page == "Overview":
    st.markdown(
        '<div class="topline"><div class="eyebrow">NETWORK INTELLIGENCE PLATFORM</div><div class="page-title">Wi-Fi Overview</div><div class="page-desc">Understand your public Wi-Fi connection, quality, and security at a glance.</div></div>',
        unsafe_allow_html=True,
    )

    result = st.session_state.get("last_result")
    net = result["network"] if result else None
    sec = result["security"] if result else None
    ai = result["ai"] if result else None

    left, right = st.columns([1.05, 1.95], gap="large")
    with left:
        st.markdown('<div class="panel-label">NETWORK HEALTH</div>', unsafe_allow_html=True)
        if net:
            subtext = ("Hasil simulasi · bukan pengukuran asli" if net.get("simulated")
                       else f"Diukur langsung · {result['location']}")
            render_speed_gauge(net["quality_score"], subtext=subtext)
            banner = f"Hasil terakhir untuk <b>{escape(result['location'])}</b>"
            if net.get("ssid") not in (None, "Tidak terhubung", "Simulasi"):
                banner += f" · SSID terdeteksi: {escape(net['ssid'])} ({escape(net.get('signal', 'N/A'))})"
            st.markdown(f'<div class="info-banner">{banner}</div>', unsafe_allow_html=True)
        else:
            render_speed_gauge(None)
            st.markdown('<div class="info-banner">Jalankan pengujian di bawah untuk melihat kualitas dan keamanan jaringan Anda.</div>', unsafe_allow_html=True)

    with right:
        render_section_heading("Connection metrics", "Core Quality of Service (QoS) measurements")
        if net:
            vals = {
                "download": f"{net['download_mbps']:.1f}",
                "upload": f"{net['upload_mbps']:.1f}",
                "ping": f"{net['ping_ms']:.0f}",
                "jitter": f"{net['jitter_ms']:.1f}",
            }
        else:
            vals = {"download": "--", "upload": "--", "ping": "--", "jitter": "--"}
        cols = st.columns(2, gap="medium")
        with cols[0]:
            render_metric_card("Download", vals["download"], "Mbps", "↓ DOWNLOAD", "↓")
            render_metric_card("Ping / Latency", vals["ping"], "ms", "◉ RESPONSE", "◌")
        with cols[1]:
            render_metric_card("Upload", vals["upload"], "Mbps", "↑ UPLOAD", "↑")
            render_metric_card("Jitter", vals["jitter"], "ms", "≈ STABILITY", "⌁")

    render_section_heading("Network assessment", "A quick look at neutrality indicators and public Wi-Fi security")
    a, b, c = st.columns(3, gap="medium")
    with a:
        if net:
            if net["is_throttled"]:
                render_status_card("NET NEUTRALITY", "Indikasi throttling",
                                   f"Streaming diperkirakan ~{net['video_mbps']:.1f} Mbps, lebih lambat dari trafik umum.",
                                   "warning")
            else:
                render_status_card("NET NEUTRALITY", "Tidak ada pembatasan",
                                   "Latensi layanan streaming setara dengan layanan umum.", "good")
        else:
            render_status_card("NET NEUTRALITY", "Awaiting test", "Traffic comparison is not available yet.")
    with b:
        if sec:
            render_status_card("WI-FI SECURITY", f"{sec['category']} · {sec['score']}/100",
                               sec["findings"][0] if sec["findings"] else "-",
                               CATEGORY_TONE.get(sec["category"], "neutral"))
        else:
            render_status_card("WI-FI SECURITY", "Awaiting audit", "Encryption and security checks will appear here.")
    with c:
        if ai:
            render_status_card("AI ADVISOR", "Gemini AI" if ai.get("source") == "ai" else "Rule-based",
                               f"{len(ai['suitable_for'])} aktivitas direkomendasikan.", "good")
        else:
            render_status_card("AI ADVISOR", "Standby", "Recommendations will appear after a scan.")

    if result:
        render_section_heading("Rekomendasi", "Ringkasan AI Advisor dan detail temuan keamanan")
        st.markdown(f'<div class="panel">{escape(ai["summary"])}</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-label" style="margin-top:14px">COCOK UNTUK</div>', unsafe_allow_html=True)
        render_activity_chips(ai["suitable_for"])
        with st.expander("Detail temuan keamanan"):
            for finding in sec["findings"]:
                st.markdown(f"- {finding}")
        if net.get("throttling_results"):
            with st.expander("Detail pengecekan layanan (net neutrality)"):
                for service, info in net["throttling_results"].items():
                    lat = info["latency"]
                    lat_str = f"{lat:.1f} ms" if isinstance(lat, float) else lat
                    st.markdown(f"- **{service}** · {info['status']} · {lat_str}")
        if result.get("scan_id"):
            st.caption(f"Tersimpan di riwayat komunitas (scan #{result['scan_id']}).")

    render_section_heading("Run a network check", "Pengujian live mengukur jaringan yang sedang Anda pakai; mode simulasi untuk demo.")
    locations = get_all_locations_summary()
    location_by_name = {loc["name"]: loc for loc in locations}

    loc_col, ssid_col = st.columns(2)
    with loc_col:
        choice = st.selectbox("LOCATION", [NEW_LOCATION] + list(location_by_name))
    with ssid_col:
        ssid = st.text_input("WI-FI NAME / SSID", placeholder="Kosongkan untuk deteksi otomatis (Windows)")

    if choice == NEW_LOCATION:
        n1, n2 = st.columns(2)
        with n1:
            new_name = st.text_input("NAMA LOKASI", placeholder="e.g. Perpustakaan UGM")
        with n2:
            new_area = st.text_input("AREA", placeholder="e.g. Bulaksumur, Sleman")
        g1, g2 = st.columns(2)
        with g1:
            new_lat = st.number_input("LATITUDE", value=DEFAULT_LAT, format="%.5f", min_value=-90.0, max_value=90.0)
        with g2:
            new_lon = st.number_input("LONGITUDE", value=DEFAULT_LON, format="%.5f", min_value=-180.0, max_value=180.0)

    mode_col, scenario_col = st.columns(2)
    with mode_col:
        mode = st.radio("MODE", ["Live (jaringan saat ini)", "Simulasi"], horizontal=True)
    simulate = None
    save = True
    if mode == "Simulasi":
        with scenario_col:
            scenario = st.selectbox("SKENARIO", list(SIMULATION_PAIRS))
            save = st.checkbox("Simpan hasil simulasi ke database", value=False)
        simulate = SIMULATION_PAIRS[scenario]

    button_col, note_col = st.columns([1, 2])
    with button_col:
        start = st.button("▶  Start network test", width="stretch")
    with note_col:
        st.caption("Pengujian live memakan waktu ±30-60 detik. Do not enter a Wi-Fi password.")

    if start:
        if choice == NEW_LOCATION:
            name = new_name.strip()
            if not name:
                st.warning("Isi nama lokasi terlebih dahulu.")
                st.stop()
            existing = find_location_by_name(name)
            if existing:
                location = {**existing, "is_new": False}
            else:
                location = {"location_id": generate_location_id(), "name": name,
                            "area": new_area.strip(), "latitude": new_lat,
                            "longitude": new_lon, "is_new": True}
        else:
            location = {**location_by_name[choice], "is_new": False}
        run_full_check(location, ssid.strip(), simulate, save)

elif page == "Community Map":
    st.markdown('<div class="topline"><div class="eyebrow">COMMUNITY NETWORK DATA</div><div class="page-title">Community Map</div><div class="page-desc">Explore public Wi-Fi quality and security reports shared by the community.</div></div>', unsafe_allow_html=True)

    locations = get_all_locations_summary()
    categories = ["Aman", "Rawan", "Bahaya"]
    selected = st.multiselect("FILTER KATEGORI KEAMANAN", categories, default=categories)
    filtered = [loc for loc in locations if loc["category"] in selected]

    scanned = [loc for loc in filtered if loc["download_mbps"] is not None]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Lokasi", len(filtered))
    m2.metric("Rata-rata Download",
              f"{sum(l['download_mbps'] for l in scanned) / len(scanned):.1f} Mbps" if scanned else "--")
    m3.metric("Lokasi Aman", sum(1 for l in filtered if l["category"] == "Aman"))
    m4.metric("Indikasi Throttling", sum(1 for l in filtered if l["is_throttled"]))

    render_section_heading("Peta komunitas", "Hijau = Aman · Kuning = Rawan · Merah = Bahaya (hasil scan terbaru tiap lokasi)")
    render_community_map(filtered)

    render_section_heading("Kecepatan vs keamanan", "Bandingkan performa dan keamanan antar lokasi")
    render_speed_security_chart(filtered)

    render_section_heading("Detail lokasi", "Ringkasan AI Advisor per lokasi")
    for loc in filtered:
        label = f"{loc['name']} · {loc['category']} ({loc['score']}/100)"
        with st.expander(label):
            st.caption(f"{loc['area']} · SSID: {loc['ssid']} · ISP: {loc['isp']} · Scan terakhir: {loc['timestamp']}")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Download", f"{loc['download_mbps']:.1f} Mbps")
            d2.metric("Upload", f"{loc['upload_mbps']:.1f} Mbps")
            d3.metric("Ping", f"{loc['ping_ms']:.0f} ms")
            d4.metric("Throttling", "Ya" if loc["is_throttled"] else "Tidak")
            st.write(loc["summary"])
            render_activity_chips(loc["suitable_for"])
            if loc["findings"]:
                st.markdown("**Temuan:** " + " · ".join(loc["findings"]))

else:
    st.markdown('<div class="topline"><div class="eyebrow">YOUR NETWORK RECORDS</div><div class="page-title">Scan History</div><div class="page-desc">Review previous network checks and compare connection quality over time.</div></div>', unsafe_allow_html=True)

    f1, f2 = st.columns([2, 1])
    history = get_scan_history(limit=500)
    with f1:
        names = sorted({h["name"] for h in history})
        location_filter = st.selectbox("LOKASI", ["Semua lokasi"] + names)
    with f2:
        limit = st.slider("JUMLAH DATA", min_value=10, max_value=500, value=50, step=10)

    if location_filter != "Semua lokasi":
        history = [h for h in history if h["name"] == location_filter]
    history = history[:limit]

    table = render_history_table(history)
    if not table.empty:
        st.download_button(
            "⬇  Unduh CSV",
            table.to_csv(index=False).encode("utf-8"),
            file_name="wifi_radar_scan_history.csv",
            mime="text/csv",
        )

st.markdown('<div class="footer">WI-FI RADAR ID · COMMUNITY-DRIVEN PUBLIC WI-FI MONITORING</div>', unsafe_allow_html=True)
