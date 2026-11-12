"""
network_scanner.py - WiFi-Radar ID (Orang 2: Network Engineer)

Kontrak output run_network_scan() (dipakai database.save_scan_result & ai_advisor):
    {
        'download_mbps': float, 'upload_mbps': float, 'ping_ms': float,
        'jitter_ms': float, 'is_throttled': bool, 'video_mbps': float,
        'quality_score': int (0-100), 'ssid': str, 'signal': str,
        'authentication': str, 'cipher': str,
        'throttling_results': dict, 'simulated': bool,
    }

Catatan: file ini menggantikan skrip lama `netscann.py` di root proyek.
"""

import platform
import re
import socket as sc
import statistics
import subprocess as sb
import time

try:
    import speedtest as sp
except ImportError:  # speedtest-cli harus ada di requirements.txt
    sp = None


# Layanan yang dibandingkan untuk indikasi throttling (net neutrality)
GENERAL_SERVICES = {
    "Google (General Web)": "google.com",
    "Cloudflare (DNS/CDN)": "cloudflare.com",
}
STREAMING_SERVICES = {
    "YouTube (Streaming)": "googlevideo.com",
    "Netflix (Streaming)": "netflix.com",
}

CONNECT_TIMEOUT = 3          # detik
SLOW_LATENCY_MS = 1500       # > 1500 ms diindikasikan lambat
THROTTLE_RATIO = 3.0         # streaming 3x lebih lambat dari layanan umum = indikasi
THROTTLE_MIN_GAP_MS = 150    # dan selisihnya minimal 150 ms (hindari false positive)
JITTER_HOST = ("1.1.1.1", 443)
JITTER_SAMPLES = 8


# ---------------------------------------------------------------------------
# Skenario simulasi (untuk demo / deploy cloud di mana speedtest diblokir)
# ---------------------------------------------------------------------------
SCENARIOS = {
    "cepat": {"download_mbps": 82.4, "upload_mbps": 61.0, "ping_ms": 9.0,
              "jitter_ms": 1.9, "is_throttled": False, "video_mbps": 80.1},
    "sedang": {"download_mbps": 34.2, "upload_mbps": 18.5, "ping_ms": 21.0,
               "jitter_ms": 4.8, "is_throttled": True, "video_mbps": 5.0},
    "lambat": {"download_mbps": 9.6, "upload_mbps": 3.1, "ping_ms": 62.0,
               "jitter_ms": 21.5, "is_throttled": True, "video_mbps": 1.8},
}


def tcp_latency_ms(host, port=443, timeout=CONNECT_TIMEOUT):
    """Ukur waktu koneksi TCP (ms). Raise socket error jika gagal."""
    start = time.perf_counter()
    with sc.create_connection((host, port), timeout=timeout):
        pass  # socket langsung ditutup oleh context manager
    return (time.perf_counter() - start) * 1000


def calculate_quality_score(download, upload, ping, jitter, is_throttled):
    """Skor kesehatan jaringan 0-100 berdasarkan QoS (bukan skor keamanan)."""
    score = 0.0
    score += min(download / 50.0, 1.0) * 40                       # Download: 40 poin
    score += min(upload / 20.0, 1.0) * 20                         # Upload: 20 poin
    score += 25 * max(0.0, min(1.0, (200 - ping) / 180.0))        # Ping <=20ms penuh
    score += 15 * max(0.0, min(1.0, (50 - jitter) / 45.0))        # Jitter <=5ms penuh
    if is_throttled:
        score -= 10
    return int(round(max(0.0, min(100.0, score))))


class NetworkDiagnostics:
    def __init__(self):
        # Atribut untuk menyimpan state / hasil pengecekan
        self.ssid = "Tidak terhubung"
        self.signal = "N/A"
        self.authentication = "Unknown"
        self.cipher = "Unknown"
        self.throttling_results = {}
        self.ping = 0.0
        self.jitter = 0.0
        self.download_speed = 0.0
        self.upload_speed = 0.0
        self.is_throttled = False
        self.video_speed = 0.0

    def check_wifi_status(self):
        """Metode untuk mengambil informasi Wi-Fi lokal menggunakan subprocess & re"""
        if platform.system() != "Windows":
            # netsh hanya ada di Windows; di Linux/Mac/cloud informasi tetap default
            return self.ssid, self.signal
        try:
            raw = sb.check_output(["netsh", "wlan", "show", "interfaces"],
                                  stderr=sb.DEVNULL, timeout=10)
            output = raw.decode("utf-8", errors="ignore")

            # Anchor ke awal baris agar tidak tertukar dengan baris "BSSID"
            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE)
            signal_match = re.search(r"^\s*(?:Signal|Sinyal)\s*:\s*(\d+)%", output, re.MULTILINE)
            auth_match = re.search(r"^\s*(?:Authentication|Autentikasi)\s*:\s*(.+)$", output, re.MULTILINE)
            cipher_match = re.search(r"^\s*(?:Cipher|Sandi)\s*:\s*(.+)$", output, re.MULTILINE)

            if ssid_match:
                self.ssid = ssid_match.group(1).strip()
            if signal_match:
                self.signal = signal_match.group(1) + "%"
            if auth_match:
                self.authentication = auth_match.group(1).strip()
            if cipher_match:
                self.cipher = cipher_match.group(1).strip()
        except Exception:
            # Jika perintah gagal (misal tidak ada adapter Wi-Fi)
            pass

        return self.ssid, self.signal

    def run_speedtest(self):
        """Metode untuk mengukur kecepatan internet menggunakan modul speedtest"""
        if sp is None:
            print("Peringatan: Modul speedtest belum diinstal. Jalankan: pip install speedtest-cli")
            return False

        print("Menghubungkan ke server Speedtest...")
        try:
            st = sp.Speedtest(secure=True)
            st.get_best_server()

            print("Mengukur kecepatan Download & Upload...")
            self.ping = float(st.results.ping)
            self.download_speed = st.download() / 1_000_000  # Mbps
            self.upload_speed = st.upload() / 1_000_000      # Mbps
            return True
        except Exception as e:
            print(f"Gagal melakukan speedtest: {e}")
            return False

    def measure_jitter(self, samples=JITTER_SAMPLES):
        """Jitter = rata-rata selisih latensi berurutan (RFC 3550 sederhana)."""
        latencies = []
        for _ in range(samples):
            try:
                latencies.append(tcp_latency_ms(*JITTER_HOST))
            except OSError:
                continue
            time.sleep(0.1)
        if len(latencies) >= 2:
            diffs = [abs(b - a) for a, b in zip(latencies, latencies[1:])]
            self.jitter = statistics.mean(diffs)
            if not self.ping:
                self.ping = statistics.median(latencies)
        return self.jitter

    def check_throttling(self):
        """Meteode pengecekan Throttling"""
        print("\nMemeriksa respons koneksi ke beberapa layanan populer...")
        target_layanan = {**GENERAL_SERVICES, **STREAMING_SERVICES}

        for nama, domain in target_layanan.items():
            try:
                # Tes koneksi soket TCP ke port 443 (HTTPS) dengan timeout 3 detik
                latency = tcp_latency_ms(domain, 443)

                # Tentukan status berdasarkan latensi (misal > 1500 ms diindikasikan lambat)
                status = "Lambat (Indikasi)" if latency > SLOW_LATENCY_MS else "Normal"

                # Simpan ke dictionary hasil
                self.throttling_results[nama] = {"status": status, "latency": latency}
            except sc.timeout:
                self.throttling_results[nama] = {"status": "Timeout / Rentan", "latency": "> 3000 ms"}
            except Exception:
                self.throttling_results[nama] = {"status": "Gagal Akses", "latency": "-"}

        self.is_throttled = self._evaluate_throttling()
        return self.throttling_results

    def _evaluate_throttling(self):
        """Bandingkan latensi layanan streaming dengan layanan umum."""
        def numeric(names):
            return [self.throttling_results[n]["latency"] for n in names
                    if isinstance(self.throttling_results.get(n, {}).get("latency"), float)]

        general = numeric(GENERAL_SERVICES)
        streaming = numeric(STREAMING_SERVICES)
        streaming_failed = any(
            not isinstance(self.throttling_results.get(n, {}).get("latency"), float)
            for n in STREAMING_SERVICES
        )

        if not general:
            return False  # internet umum juga gagal -> bukan throttling spesifik
        if streaming_failed:
            return True   # web umum bisa, streaming tidak bisa -> indikasi pembatasan
        g, s = statistics.median(general), statistics.median(streaming)
        return s > g * THROTTLE_RATIO and (s - g) > THROTTLE_MIN_GAP_MS

    def estimate_video_speed(self):
        """Estimasi throughput streaming (bukan pengukuran langsung).

        Jika tidak ada indikasi throttling, diasumsikan sama dengan download.
        Jika ada, diskalakan dengan rasio latensi layanan umum vs streaming.
        """
        if not self.is_throttled:
            self.video_speed = self.download_speed
            return self.video_speed

        general = [v["latency"] for k, v in self.throttling_results.items()
                   if k in GENERAL_SERVICES and isinstance(v["latency"], float)]
        streaming = [v["latency"] for k, v in self.throttling_results.items()
                     if k in STREAMING_SERVICES and isinstance(v["latency"], float)]
        if general and streaming:
            ratio = statistics.median(general) / statistics.median(streaming)
            self.video_speed = self.download_speed * max(0.05, min(1.0, ratio))
        else:
            self.video_speed = self.download_speed * 0.1
        return self.video_speed

    def to_dict(self, simulated=False):
        """Kembalikan hasil sesuai kontrak data untuk database.py / ai_advisor.py."""
        return {
            "download_mbps": round(self.download_speed, 2),
            "upload_mbps": round(self.upload_speed, 2),
            "ping_ms": round(self.ping, 1),
            "jitter_ms": round(self.jitter, 1),
            "is_throttled": bool(self.is_throttled),
            "video_mbps": round(self.video_speed, 2),
            "quality_score": calculate_quality_score(
                self.download_speed, self.upload_speed, self.ping, self.jitter, self.is_throttled
            ),
            "ssid": self.ssid,
            "signal": self.signal,
            "authentication": self.authentication,
            "cipher": self.cipher,
            "throttling_results": self.throttling_results,
            "simulated": simulated,
        }

    def display_results(self):
        """Metode untuk mencetak seluruh hasil diagnostik"""
        print("\n" + "=" * 35)
        print("     HASIL DIAGNOSTIK JARINGAN")
        print("=" * 35)
        print(f"Nama Wi-Fi (SSID) : {self.ssid}")
        print(f"Kekuatan Sinyal   : {self.signal}")
        print(f"Autentikasi       : {self.authentication} ({self.cipher})")
        if sp:
            print(f"Ping              : {self.ping:.2f} ms")
            print(f"Jitter            : {self.jitter:.2f} ms")
            print(f"Kecepatan Download: {self.download_speed:.2f} Mbps")
            print(f"Kecepatan Upload  : {self.upload_speed:.2f} Mbps")
        print("=" * 60)
        print("Layanan\t\t\t\tStatus\t\tLatensi (Ping)")
        print("=" * 60)

        for nama, data in self.throttling_results.items():
            lat = data["latency"]
            lat_str = f"{lat:.1f} ms" if isinstance(lat, float) else lat
            print(f"{nama:<25} | {data['status']:<18} | {lat_str}")

        print(f"\nIndikasi throttling: {'YA' if self.is_throttled else 'Tidak'}")
        print("\n[+] Analisis Net Neutrality Selesai.")
        print(
            "[INFO] Jika latensi streaming atau kecepatan unduh turun drastis"
            " dibandingkan baseline tanpa alasan yang jelas, ada indikasi"
            " pembatasan (throttling) oleh ISP."
        )


def run_network_scan(simulate=None):
    """Fungsi utama untuk app.py.

    simulate: None (pengukuran asli) atau 'cepat' / 'sedang' / 'lambat'.
    Raise RuntimeError jika speedtest asli gagal, supaya app tidak menyimpan data palsu.
    """
    if simulate is not None:
        if simulate not in SCENARIOS:
            raise ValueError(f"Skenario harus salah satu dari {list(SCENARIOS)}")
        data = dict(SCENARIOS[simulate])
        data.update({
            "quality_score": calculate_quality_score(
                data["download_mbps"], data["upload_mbps"], data["ping_ms"],
                data["jitter_ms"], data["is_throttled"]),
            "ssid": "Simulasi", "signal": "N/A",
            "authentication": "Unknown", "cipher": "Unknown",
            "throttling_results": {}, "simulated": True,
        })
        return data

    diag = NetworkDiagnostics()
    diag.check_wifi_status()
    if not diag.run_speedtest():
        raise RuntimeError(
            "Speedtest gagal dijalankan. Pastikan terhubung ke internet dan "
            "paket `speedtest-cli` terpasang, atau gunakan mode simulasi."
        )
    diag.measure_jitter()
    diag.check_throttling()
    diag.estimate_video_speed()
    return diag.to_dict(simulated=False)


# --- Bagian Eksekusi Program ---
if __name__ == "__main__":
    # 1. Inisialisasi Objek dari Class NetworkDiagnostics
    diagnostic = NetworkDiagnostics()

    # 2. Menjalankan proses pengecekan Wi-Fi lokal
    print("Mendeteksi status Wi-Fi lokal...")
    diagnostic.check_wifi_status()

    # 3. Menjalankan speedtest internet
    diagnostic.run_speedtest()
    diagnostic.measure_jitter()

    # 4. Menjalankan throttling
    diagnostic.check_throttling()
    diagnostic.estimate_video_speed()

    # 5. Menampilkan hasil akhir
    diagnostic.display_results()
    print("\nKontrak data:", diagnostic.to_dict())
