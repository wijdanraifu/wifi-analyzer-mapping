import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

# Path dihitung relatif terhadap root proyek (bukan working directory), sehingga
# `streamlit run app.py` maupun `python modules/database.py` sama-sama menemukan file.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "wifi_radar.db")
SEED_FILE_PATH = os.path.join(DATA_DIR, "seed_data.json")


def get_connection() -> sqlite3.Connection:
    """Membuka koneksi ke database SQLite dengan Row Factory berbentuk dictionary."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Task 1.3: Membuat skema tabel SQLite:
    - Tabel Statis: locations_master & security_rules
    - Tabel Dinamis: wifi_scan_logs
    Serta mengisi data awal dari seed_data.json jika tabel masih kosong.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabel Statis: locations_master
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations_master (
            location_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            area TEXT NOT NULL,
            ssid TEXT NOT NULL,
            isp TEXT DEFAULT 'Unknown',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
    """)

    # 2. Tabel Statis: security_rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_rules (
            rule_id TEXT PRIMARY KEY,
            parameter TEXT NOT NULL,
            condition TEXT NOT NULL,
            penalty_points INTEGER NOT NULL,
            risk_description TEXT NOT NULL
        )
    """)

    # 3. Tabel Dinamis: wifi_scan_logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wifi_scan_logs (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            download_mbps REAL NOT NULL,
            upload_mbps REAL NOT NULL,
            ping_ms REAL NOT NULL,
            jitter_ms REAL DEFAULT 0.0,
            is_throttled INTEGER NOT NULL,
            video_mbps REAL DEFAULT 0.0,
            score INTEGER NOT NULL,
            category TEXT NOT NULL,
            findings TEXT NOT NULL,
            summary TEXT NOT NULL,
            suitable_for TEXT NOT NULL,
            FOREIGN KEY (location_id) REFERENCES locations_master (location_id)
        )
    """)

    conn.commit()
    conn.close()

    # Muat seed_data.json jika tabel locations_master masih kosong
    seed_initial_data()


def seed_initial_data() -> None:
    """Memuat data dari seed_data.json ke dalam SQLite jika belum ada data."""
    if not os.path.exists(SEED_FILE_PATH):
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM locations_master")
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return

    with open(SEED_FILE_PATH, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    # Masukkan data ke security_rules
    for rule in seed_data.get("security_rules", []):
        cursor.execute("""
            INSERT OR IGNORE INTO security_rules (rule_id, parameter, condition, penalty_points, risk_description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rule["rule_id"],
            rule["parameter"],
            rule["condition"],
            rule["penalty_points"],
            rule["risk_description"]
        ))

    # Masukkan data ke locations_master & wifi_scan_logs awal
    for loc in seed_data.get("locations_master", []):
        cursor.execute("""
            INSERT OR IGNORE INTO locations_master (location_id, name, area, ssid, isp, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            loc["location_id"],
            loc["name"],
            loc["area"],
            loc["ssid"],
            loc.get("isp", "Unknown"),
            loc["latitude"],
            loc["longitude"]
        ))

        scan = loc.get("initial_scan")
        if scan:
            cursor.execute("""
                INSERT INTO wifi_scan_logs (
                    location_id, timestamp, download_mbps, upload_mbps, ping_ms, jitter_ms,
                    is_throttled, video_mbps, score, category, findings, summary, suitable_for
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                loc["location_id"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                float(scan["download_mbps"]),
                float(scan["upload_mbps"]),
                float(scan["ping_ms"]),
                float(scan.get("jitter_ms", 0.0)),
                1 if scan["is_throttled"] else 0,
                float(scan.get("video_mbps", 0.0)),
                int(scan["score"]),
                scan["category"],
                json.dumps(scan.get("findings", []), ensure_ascii=False),
                scan["summary"],
                json.dumps(scan.get("suitable_for", []), ensure_ascii=False)
            ))

    conn.commit()
    conn.close()


def save_scan_result(
    location_id: str,
    network_data: Dict[str, Any],
    security_data: Dict[str, Any],
    ai_data: Dict[str, Any],
    new_location_info: Optional[Dict[str, Any]] = None
) -> int:
    """
    Task 1.4: Menyimpan hasil pengujian baru (Auto-Save) ke wifi_scan_logs.
    Menerima kontrak data langsung dari modul Orang 2, Orang 3, dan Orang 4:
    - network_data (Orang 2): {'download_mbps': float, 'upload_mbps': float, 'ping_ms': float, 'is_throttled': bool, ...}
    - security_data (Orang 3): {'score': int(0-100), 'category': str, 'findings': list[str]}
    - ai_data (Orang 4): {'summary': str, 'suitable_for': list[str]}
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Jika pengguna memindai di lokasi baru yang belum ada di locations_master
    if new_location_info:
        cursor.execute("""
            INSERT OR IGNORE INTO locations_master (location_id, name, area, ssid, isp, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            location_id,
            new_location_info.get("name", "Lokasi Baru"),
            new_location_info.get("area", "Yogyakarta"),
            new_location_info.get("ssid", "Public_WiFi"),
            new_location_info.get("isp", "Unknown"),
            float(new_location_info.get("latitude", -7.76951)),
            float(new_location_info.get("longitude", 110.37825))
        ))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO wifi_scan_logs (
            location_id, timestamp, download_mbps, upload_mbps, ping_ms, jitter_ms,
            is_throttled, video_mbps, score, category, findings, summary, suitable_for
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        location_id,
        timestamp,
        float(network_data.get("download_mbps", 0.0)),
        float(network_data.get("upload_mbps", 0.0)),
        float(network_data.get("ping_ms", 0.0)),
        float(network_data.get("jitter_ms", 0.0)),
        1 if network_data.get("is_throttled", False) else 0,
        float(network_data.get("video_mbps", 0.0)),
        int(security_data.get("score", 0)),
        str(security_data.get("category", "Rawan")),
        json.dumps(security_data.get("findings", []), ensure_ascii=False),
        str(ai_data.get("summary", "")),
        json.dumps(ai_data.get("suitable_for", []), ensure_ascii=False)
    ))

    scan_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scan_id


def get_all_locations_summary() -> List[Dict[str, Any]]:
    """
    Task 1.4: Mengembalikan List of Dict berisi ringkasan hasil scan terbaru untuk tiap lokasi.
    Output ini dirancang khusus untuk dikonsumsi visualizer.py (Orang 5) guna merender:
    - Peta interaktif dengan pin warna (Hijau/Kuning/Merah)
    - Grafik bar perbandingan kecepatan vs keamanan
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Mengambil data lokasi digabung dengan log pengujian paling baru di masing-masing lokasi
    query = """
        SELECT 
            m.location_id, m.name, m.area, m.ssid, m.isp, m.latitude, m.longitude,
            l.scan_id, l.timestamp, l.download_mbps, l.upload_mbps, l.ping_ms, l.jitter_ms,
            l.is_throttled, l.video_mbps, l.score, l.category, l.findings, l.summary, l.suitable_for
        FROM locations_master m
        LEFT JOIN wifi_scan_logs l ON l.scan_id = (
            SELECT scan_id FROM wifi_scan_logs 
            WHERE location_id = m.location_id 
            ORDER BY scan_id DESC LIMIT 1
        )
        ORDER BY l.download_mbps IS NULL, l.download_mbps DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        item = dict(row)
        item["is_throttled"] = bool(item["is_throttled"])
        item["findings"] = json.loads(item["findings"]) if item["findings"] else []
        item["suitable_for"] = json.loads(item["suitable_for"]) if item["suitable_for"] else []
        results.append(item)

    return results


def find_location_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Mencari lokasi di locations_master berdasarkan nama (tidak peka huruf besar/kecil)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM locations_master WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) LIMIT 1",
        (name,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def generate_location_id() -> str:
    """Membuat location_id baru berurutan, misal LOC-010."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT location_id FROM locations_master WHERE location_id LIKE 'LOC-%'")
    numbers = []
    for row in cursor.fetchall():
        try:
            numbers.append(int(row["location_id"].split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    conn.close()
    return f"LOC-{(max(numbers) + 1) if numbers else 1:03d}"


def get_scan_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Mengambil seluruh riwayat pengujian untuk ditampilkan pada tabel riwayat komunitas."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            l.scan_id, l.timestamp, m.location_id, m.name, m.area, m.ssid, m.isp,
            m.latitude, m.longitude, l.download_mbps, l.upload_mbps, l.ping_ms, l.jitter_ms,
            l.is_throttled, l.video_mbps, l.score, l.category, l.findings, l.summary, l.suitable_for
        FROM wifi_scan_logs l
        JOIN locations_master m ON l.location_id = m.location_id
        ORDER BY l.scan_id DESC
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        item = dict(row)
        item["is_throttled"] = bool(item["is_throttled"])
        item["findings"] = json.loads(item["findings"]) if item["findings"] else []
        item["suitable_for"] = json.loads(item["suitable_for"]) if item["suitable_for"] else []
        history.append(item)

    return history


def get_security_rules() -> List[Dict[str, Any]]:
    """Mengambil daftar aturan standar penilaian keamanan dari tabel statis security_rules."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM security_rules")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# Blok pengujian mandiri: jalankan `python database.py` di terminal untuk menguji fungsi
if __name__ == "__main__":
    print("Menginisialisasi database dan memuat seed_data.json...")
    init_db()
    
    locations = get_all_locations_summary()
    print(f"Berhasil memuat {len(locations)} titik lokasi Wi-Fi:")
    for loc in locations:
        status_throttle = "Throttled" if loc["is_throttled"] else "Normal"
        print(f"- {loc['name']} ({loc['ssid']}): {loc['download_mbps']} Mbps | Skor Keamanan: {loc['score']}/100 ({loc['category']}) | {status_throttle}")
