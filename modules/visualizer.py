"""Reusable UI components for WiFi-Radar ID's Streamlit dashboard."""

from __future__ import annotations

from html import escape
from typing import Any

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

# Warna pin peta per kategori keamanan (RGB)
CATEGORY_COLORS = {
    "Aman": [57, 214, 162],
    "Rawan": [245, 184, 75],
    "Bahaya": [240, 90, 90],
}
UNKNOWN_COLOR = [130, 149, 170]
CATEGORY_TONE = {"Aman": "good", "Rawan": "warning", "Bahaya": "danger"}


def _e(value: Any) -> str:
    """Escape teks sebelum dimasukkan ke HTML (input pengguna seperti SSID/lokasi)."""
    return escape(str(value), quote=True)


def render_speed_gauge(
    value: float | None = None,
    label: str = "NETWORK SCORE",
    subtext: str | None = None,
) -> None:
    """Render a clean circular gauge. None means no scan has been run yet."""
    if value is None:
        value_text = "--"
        progress = 0
        subtext = subtext or "Belum ada pengujian"
    else:
        progress = max(0, min(100, int(value)))
        value_text = str(progress)
        subtext = subtext or "Skor kualitas jaringan (QoS)"

    # Lingkaran gauge hanya 270 derajat (75% dari conic-gradient)
    arc = progress * 0.75

    st.markdown(
        f"""
        <div class="gauge-wrap">
          <div class="gauge" style="--progress:{arc}%">
            <div class="gauge-inner">
              <div class="gauge-label">{_e(label)}</div>
              <div class="gauge-value">{value_text}<span>{' / 100' if value is not None else ''}</span></div>
              <div class="gauge-unit">{ 'NETWORK HEALTH' if value is not None else 'READY TO TEST' }</div>
            </div>
          </div>
          <div class="gauge-subtext">{_e(subtext)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, unit: str, note: str, icon: str) -> None:
    """Render one compact metric card."""
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-top"><span class="metric-icon">{_e(icon)}</span><span class="metric-note">{_e(note)}</span></div>
          <div class="metric-title">{_e(title)}</div>
          <div class="metric-value">{_e(value)}<span> {_e(unit)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="section-subtitle">{_e(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="section-heading"><div class="section-title">{_e(title)}</div>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def render_status_card(title: str, status: str, detail: str, tone: str = "neutral") -> None:
    """tone can be: good, warning, danger, neutral."""
    tone = tone if tone in {"good", "warning", "danger", "neutral"} else "neutral"
    st.markdown(
        f"""
        <div class="status-card {tone}">
          <div class="status-dot"></div>
          <div class="status-copy"><div class="status-title">{_e(title)}</div>
          <div class="status-value">{_e(status)}</div><div class="status-detail">{_e(detail)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_activity_chips(activities: list[str]) -> None:
    """Tampilkan daftar aktivitas yang cocok sebagai chip."""
    if not activities:
        st.markdown('<div class="chip chip-empty">Tidak direkomendasikan untuk aktivitas penting</div>',
                    unsafe_allow_html=True)
        return
    chips = "".join(f'<span class="chip">{_e(a)}</span>' for a in activities)
    st.markdown(f'<div class="chip-row">{chips}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Community Map & Charts (data dari database.get_all_locations_summary())
# ---------------------------------------------------------------------------
def locations_to_dataframe(locations: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(locations)
    if df.empty:
        return df
    df["category"] = df["category"].fillna("Belum dipindai")
    df["color"] = df["category"].map(lambda c: CATEGORY_COLORS.get(c, UNKNOWN_COLOR))
    df["suitable_text"] = df["suitable_for"].map(
        lambda items: ", ".join(items) if items else "-")
    for col in ("download_mbps", "upload_mbps", "ping_ms", "score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def render_community_map(locations: list[dict]) -> None:
    """Peta interaktif dengan pin Hijau (Aman) / Kuning (Rawan) / Merah (Bahaya)."""
    df = locations_to_dataframe(locations)
    if df.empty:
        st.info("Belum ada data lokasi untuk ditampilkan di peta.")
        return

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_radius=60,
        radius_min_pixels=7,
        radius_max_pixels=18,
        pickable=True,
        stroked=True,
        get_line_color=[8, 15, 28],
        line_width_min_pixels=1,
    )
    view = pdk.ViewState(
        latitude=float(df["latitude"].mean()),
        longitude=float(df["longitude"].mean()),
        zoom=13.5,
        pitch=0,
    )
    tooltip = {
        "html": "<b>{name}</b><br/>{ssid} · {isp}<br/>"
                "Download: {download_mbps} Mbps · Ping: {ping_ms} ms<br/>"
                "Keamanan: {score}/100 ({category})",
        "style": {"backgroundColor": "#142238", "color": "#f4f8ff"},
    }
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip,
                             map_style=None))

    legend = "".join(
        f'<span class="legend-item"><span class="legend-dot" '
        f'style="background:rgb({c[0]},{c[1]},{c[2]})"></span>{name}</span>'
        for name, c in CATEGORY_COLORS.items()
    )
    st.markdown(f'<div class="legend">{legend}</div>', unsafe_allow_html=True)


def render_speed_security_chart(locations: list[dict]) -> None:
    """Grafik bar perbandingan kecepatan download vs skor keamanan per lokasi."""
    df = locations_to_dataframe(locations)
    if df.empty or df["download_mbps"].isna().all():
        st.info("Belum ada hasil pengujian untuk dibandingkan.")
        return

    df = df.dropna(subset=["download_mbps"])
    color_scale = alt.Scale(
        domain=list(CATEGORY_COLORS),
        range=[f"rgb({c[0]},{c[1]},{c[2]})" for c in CATEGORY_COLORS.values()],
    )
    sort_order = df.sort_values("download_mbps", ascending=False)["name"].tolist()

    speed = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("download_mbps:Q", title="Download (Mbps)"),
            y=alt.Y("name:N", sort=sort_order, title=None),
            color=alt.Color("category:N", scale=color_scale, title="Keamanan"),
            tooltip=["name", "ssid", "download_mbps", "upload_mbps", "ping_ms", "score", "category"],
        )
        .properties(title="Kecepatan Download", height=max(220, 34 * len(df)))
    )
    security = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("score:Q", title="Skor Keamanan (0-100)", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("name:N", sort=sort_order, title=None, axis=None),
            color=alt.Color("category:N", scale=color_scale, legend=None),
            tooltip=["name", "score", "category"],
        )
        .properties(title="Skor Keamanan", height=max(220, 34 * len(df)))
    )
    chart = alt.hconcat(speed, security).configure_view(stroke=None).configure(background="transparent")
    st.altair_chart(chart, width="stretch")


def render_history_table(history: list[dict]) -> pd.DataFrame:
    """Tabel riwayat pengujian. Mengembalikan DataFrame (untuk unduh CSV)."""
    df = pd.DataFrame(history)
    if df.empty:
        st.info("Belum ada riwayat pengujian.")
        return df

    table = pd.DataFrame({
        "Waktu": df["timestamp"],
        "Lokasi": df["name"],
        "SSID": df["ssid"],
        "Download (Mbps)": df["download_mbps"],
        "Upload (Mbps)": df["upload_mbps"],
        "Ping (ms)": df["ping_ms"],
        "Jitter (ms)": df["jitter_ms"],
        "Throttling": df["is_throttled"].map({True: "Ya", False: "Tidak"}),
        "Skor Keamanan": df["score"],
        "Kategori": df["category"],
        "Cocok Untuk": df["suitable_for"].map(lambda x: ", ".join(x) if x else "-"),
    })
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "Skor Keamanan": st.column_config.ProgressColumn(
                "Skor Keamanan", min_value=0, max_value=100, format="%d"),
        },
    )
    return table
