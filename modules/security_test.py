"""
security_test.py - WiFi-Radar ID (Orang 3: Cybersecurity Auditor)

Kontrak output (JANGAN diubah tanpa kabari tim):
    {'score': int (0-100), 'category': 'Aman' | 'Rawan' | 'Bahaya', 'findings': list[str]}

Alur:
    check_wifi_encryption()    -> observasi enkripsi router (Open/WEP/WPA2/WPA3)
    check_dns_and_ssl()        -> observasi DNS + SSL/TLS
    check_security_headers()   -> observasi header keamanan + captive portal
    calculate_security_score() -> gabungkan observasi jadi skor, kategori, temuan
    audit_wifi()               -> fungsi utama yang dipanggil app.py / ai_advisor.py
"""

import socket
import ssl
import time

try:
    import requests
except ImportError:  # requests harus ada di python_library_list.txt
    requests = None


# ---------------------------------------------------------------------------
# TASK 3.1 - BOBOT SKOR (mulai dari 100, dikurangi per temuan)
# ---------------------------------------------------------------------------
PENALTIES = {
    "wifi_open":          (45, "Wi-Fi terbuka tanpa enkripsi/password; lalu lintas mudah disadap (sniffing)."),
    "wifi_weak":          (20, "Enkripsi Wi-Fi usang (WEP/WPA-TKIP), mudah dibobol."),
    "ssl_invalid":        (40, "Sertifikat SSL tidak valid atau gagal diverifikasi (risiko MITM)."),
    "ssl_expired":        (40, "Sertifikat SSL sudah kedaluwarsa."),
    "tls_outdated":       (15, "Versi TLS di bawah 1.2 (enkripsi lemah)."),
    "dns_mismatch":       (25, "Jawaban DNS berbeda dari resolver terpercaya (indikasi DNS hijack)."),
    "captive_portal":     (5,  "Terdeteksi captive portal (halaman login Wi-Fi)."),
    "portal_insecure":    (15, "Captive portal memakai HTTP biasa, kredensial bisa disadap."),
    "no_hsts":            (10, "Header HSTS tidak ada."),
    "no_csp":             (5,  "Header Content-Security-Policy tidak ada."),
    "no_xfo":             (5,  "Header X-Frame-Options tidak ada."),
    "no_xcto":            (5,  "Header X-Content-Type-Options tidak ada."),
    "check_failed":       (10, "Sebagian pemeriksaan gagal dijalankan (koneksi bermasalah)."),
}

THRESHOLD_AMAN = 80    # 80-100 -> Aman
THRESHOLD_RAWAN = 50   # 50-79  -> Rawan, di bawah 50 -> Bahaya

TIMEOUT = 8  # detik


# ---------------------------------------------------------------------------
# SKENARIO SIMULASI (Task 3.5 + fallback saat deploy di cloud)
# ---------------------------------------------------------------------------
SCENARIOS = {
    "aman": {
        "wifi_open": False, "wifi_weak": False,
        "ssl_invalid": False, "ssl_expired": False, "tls_outdated": False,
        "dns_mismatch": False, "captive_portal": False, "portal_insecure": False,
        "no_hsts": False, "no_csp": False, "no_xfo": False, "no_xcto": False,
        "check_failed": False,
    },
    "rawan": {
        "wifi_open": False, "wifi_weak": False,
        "ssl_invalid": False, "ssl_expired": False, "tls_outdated": False,
        "dns_mismatch": False, "captive_portal": True, "portal_insecure": True,
        "no_hsts": True, "no_csp": True, "no_xfo": True, "no_xcto": False,
        "check_failed": False,
    },
    "bahaya": {
        "wifi_open": True, "wifi_weak": False,
        "ssl_invalid": True, "ssl_expired": False, "tls_outdated": True,
        "dns_mismatch": True, "captive_portal": True, "portal_insecure": True,
        "no_hsts": True, "no_csp": True, "no_xfo": True, "no_xcto": True,
        "check_failed": False,
    },
}


# ---------------------------------------------------------------------------
# TASK 3.2 - DNS dan SSL/TLS
# ---------------------------------------------------------------------------
def check_ssl(hostname="www.google.com"):
    """Cek validitas sertifikat, masa berlaku, dan versi TLS."""
    result = {"ssl_invalid": False, "ssl_expired": False,
              "tls_outdated": False, "tls_version": None, "check_failed": False}
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                result["tls_version"] = ssock.version()
                cert = ssock.getpeercert()
                expiry = ssl.cert_time_to_seconds(cert["notAfter"])
                if expiry < time.time():
                    result["ssl_expired"] = True
                if result["tls_version"] in ("TLSv1", "TLSv1.1", "SSLv3"):
                    result["tls_outdated"] = True
    except ssl.SSLCertVerificationError as e:
        if e.verify_code == 10:  # 10 = sertifikat kedaluwarsa
            result["ssl_expired"] = True
        else:
            result["ssl_invalid"] = True
    except (socket.timeout, socket.gaierror, ConnectionError, OSError):
        result["check_failed"] = True
    return result


def check_dns(domain="example.com"):
    """Bandingkan jawaban DNS Wi-Fi dengan DNS-over-HTTPS (port 443).

    DNS biasa ke resolver publik (port 53) sering diblokir di jaringan
    kampus/kos, jadi resolver terpercaya ditanya lewat HTTPS. Catatan: domain
    di belakang CDN bisa memberi IP berbeda tanpa ada serangan, jadi mismatch
    hanya dihitung jika tidak ada satu pun IP yang beririsan.
    """
    result = {"dns_mismatch": False, "check_failed": False}
    if requests is None:
        result["check_failed"] = True
        return result
    try:
        local_ips = {info[4][0] for info in socket.getaddrinfo(domain, 80, socket.AF_INET)}
        trusted_ips = set()
        for url, headers in (
            ("https://cloudflare-dns.com/dns-query", {"accept": "application/dns-json"}),
            ("https://dns.google/resolve", {}),
        ):
            try:
                resp = requests.get(url, params={"name": domain, "type": "A"},
                                    headers=headers, timeout=TIMEOUT)
                answers = resp.json().get("Answer", [])
                trusted_ips = {a["data"] for a in answers if a.get("type") == 1}
                if trusted_ips:
                    break
            except (requests.RequestException, ValueError):
                continue
        if not trusted_ips:
            result["check_failed"] = True
        elif local_ips.isdisjoint(trusted_ips):
            result["dns_mismatch"] = True
    except OSError:
        result["check_failed"] = True
    return result


def check_dns_and_ssl(hostname="www.google.com", dns_domain="example.com"):
    """Gabungan pemeriksaan DNS + SSL/TLS."""
    ssl_res = check_ssl(hostname)
    dns_res = check_dns(dns_domain)
    merged = {**ssl_res, **dns_res}
    merged["check_failed"] = ssl_res["check_failed"] or dns_res["check_failed"]
    return merged


# ---------------------------------------------------------------------------
# TASK 3.2b - Enkripsi router Wi-Fi (sesuai rule ENC_OPEN di seed_data.json)
# ---------------------------------------------------------------------------
def check_wifi_encryption(wifi_info=None):
    """Nilai enkripsi Wi-Fi dari hasil `netsh` (network_scanner).

    wifi_info: dict berisi 'authentication' & 'cipher'. Jika None, dibaca langsung.
    Jika informasi tidak tersedia (bukan Windows / cloud), tidak diberi penalti.
    """
    result = {"wifi_open": False, "wifi_weak": False}
    if wifi_info is None:
        try:
            from modules.network_scanner import NetworkDiagnostics
        except ImportError:
            from network_scanner import NetworkDiagnostics
        diag = NetworkDiagnostics()
        diag.check_wifi_status()
        wifi_info = {"authentication": diag.authentication, "cipher": diag.cipher}

    auth = str(wifi_info.get("authentication", "Unknown")).lower()
    cipher = str(wifi_info.get("cipher", "Unknown")).lower()
    if auth.startswith("open") or cipher == "none":
        result["wifi_open"] = True
    elif "wep" in cipher or "tkip" in cipher or auth in ("wpa-personal", "wpa-enterprise"):
        result["wifi_weak"] = True
    return result


# ---------------------------------------------------------------------------
# TASK 3.3 - Header keamanan + captive portal
# ---------------------------------------------------------------------------
def check_captive_portal():
    """Request ke URL yang normalnya membalas 204. Selain itu = kemungkinan portal."""
    result = {"captive_portal": False, "portal_insecure": False, "check_failed": False}
    if requests is None:
        result["check_failed"] = True
        return result
    try:
        resp = requests.get("http://connectivitycheck.gstatic.com/generate_204",
                            allow_redirects=False, timeout=TIMEOUT)
        if resp.status_code != 204:
            result["captive_portal"] = True
            location = resp.headers.get("Location", "")
            if location.startswith("http://"):
                result["portal_insecure"] = True
    except requests.RequestException:
        result["check_failed"] = True
    return result


def check_security_headers(url="https://www.google.com"):
    """Cek header keamanan + captive portal."""
    result = {"no_hsts": False, "no_csp": False, "no_xfo": False,
              "no_xcto": False, "check_failed": False}
    if requests is None:
        result["check_failed"] = True
    else:
        try:
            headers = requests.get(url, timeout=TIMEOUT).headers
            result["no_hsts"] = "Strict-Transport-Security" not in headers
            result["no_csp"] = "Content-Security-Policy" not in headers
            result["no_xfo"] = "X-Frame-Options" not in headers
            result["no_xcto"] = "X-Content-Type-Options" not in headers
        except requests.RequestException:
            result["check_failed"] = True

    portal = check_captive_portal()
    result.update({"captive_portal": portal["captive_portal"],
                   "portal_insecure": portal["portal_insecure"]})
    result["check_failed"] = result["check_failed"] or portal["check_failed"]
    return result


# ---------------------------------------------------------------------------
# TASK 3.4 - Skor
# ---------------------------------------------------------------------------
def calculate_security_score(observations):
    """Ubah observasi (dict flag boolean) jadi output sesuai kontrak data."""
    score = 100
    findings = []
    for key, (penalty, message) in PENALTIES.items():
        if observations.get(key):
            score -= penalty
            findings.append(f"{message} (-{penalty})")
    score = max(0, min(100, score))

    if score >= THRESHOLD_AMAN:
        category = "Aman"
    elif score >= THRESHOLD_RAWAN:
        category = "Rawan"
    else:
        category = "Bahaya"

    if not findings:
        findings.append("Tidak ada temuan keamanan.")
    return {"score": int(score), "category": category, "findings": findings}


# ---------------------------------------------------------------------------
# Fungsi utama untuk app.py / ai_advisor.py
# ---------------------------------------------------------------------------
def audit_wifi(simulate=None, wifi_info=None):
    """Jalankan audit. simulate: None (asli) atau 'aman' / 'rawan' / 'bahaya'.

    wifi_info (opsional): dict 'authentication'/'cipher' dari network_scanner
    agar `netsh` tidak dijalankan dua kali.
    """
    if simulate is not None:
        if simulate not in SCENARIOS:
            raise ValueError(f"Skenario harus salah satu dari {list(SCENARIOS)}")
        return calculate_security_score(SCENARIOS[simulate])

    observations = {}
    observations.update(check_wifi_encryption(wifi_info))
    observations.update(check_dns_and_ssl())
    header_obs = check_security_headers()
    failed = observations.get("check_failed") or header_obs["check_failed"]
    observations.update(header_obs)
    observations["check_failed"] = failed
    return calculate_security_score(observations)


if __name__ == "__main__":
    for name in SCENARIOS:
        print(name, "->", audit_wifi(simulate=name))
    print("asli ->", audit_wifi())
