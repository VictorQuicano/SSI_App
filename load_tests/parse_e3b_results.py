"""
Procesa e3b_stats_history.csv → muestra throughput y latencia por nivel de carga.

Ejecutar después del test:
  python load_tests/parse_e3b_results.py
"""

import csv, pathlib, json
from collections import defaultdict

HISTORY_FILE = pathlib.Path(__file__).parent / "resultados/e3b_stats_history.csv"
if not HISTORY_FILE.exists():
    raise FileNotFoundError("No se encontró e3b_stats_history.csv. ¿Ejecutaste el test?")

# Pasos y sus rangos de tiempo (en segundos desde T=0)
# Usamos la SEGUNDA MITAD de cada paso para evitar el transitorio de rampa
STAGES = [
    {"users":  1, "t_start":  60, "t_end": 120},
    {"users":  3, "t_start": 180, "t_end": 240},
    {"users":  5, "t_start": 300, "t_end": 360},
    {"users": 10, "t_start": 450, "t_end": 570},
    {"users": 15, "t_start": 600, "t_end": 720},
    {"users": 20, "t_start": 780, "t_end": 900},
    {"users": 30, "t_start": 870, "t_end": 1020},
]

# ── Leer CSV ──────────────────────────────────────────────────────────────────
# Columnas: Timestamp,User count,Type,Name,Requests/s,Failures/s,
#           50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%,Total Request Count,Total Failure Count
rows = []
with open(HISTORY_FILE) as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["Type"] == "ETH" and row["Name"] in ("createReservation","startTrip","completeTrip"):
            rows.append({
                "t":       float(row["Timestamp"]),
                "name":    row["Name"],
                "rps":     float(row["Requests/s"]),
                "fail_s":  float(row["Failures/s"]),
                "p50":     float(row["50%"]) if row["50%"] != "N/A" else None,
                "p95":     float(row["95%"]) if row["95%"] != "N/A" else None,
                "p99":     float(row["99%"]) if row["99%"] != "N/A" else None,
            })

if not rows:
    print("WARN: No se encontraron filas ETH en el CSV.")
    raise SystemExit(1)

# Normalizar timestamps al inicio del test
t0 = min(r["t"] for r in rows)
for r in rows:
    r["t"] -= t0

# ── Calcular métricas por paso ────────────────────────────────────────────────
results = []
print(f"\n{'u':>4} {'Operación':>22} {'rps':>6} {'fail%':>7} {'p50':>7} {'p95':>7}")
print("-" * 60)

for stage in STAGES:
    t_start, t_end = stage["t_start"], stage["t_end"]
    u = stage["users"]

    stage_data = {}
    for name in ("createReservation", "startTrip", "completeTrip"):
        window = [r for r in rows
                  if r["name"] == name and t_start <= r["t"] <= t_end]
        if not window:
            stage_data[name] = None
            continue
        rps      = sum(r["rps"]    for r in window) / len(window)
        fail_s   = sum(r["fail_s"] for r in window) / len(window)
        fail_pct = (fail_s / rps * 100) if rps > 0 else 0
        p50s = [r["p50"] for r in window if r["p50"] is not None]
        p95s = [r["p95"] for r in window if r["p95"] is not None]
        p50 = sum(p50s) / len(p50s) if p50s else None
        p95 = sum(p95s) / len(p95s) if p95s else None
        stage_data[name] = {"rps": rps, "fail_pct": fail_pct, "p50": p50, "p95": p95}
        p50_str = f"{p50:.0f}" if p50 else "N/A"
        p95_str = f"{p95:.0f}" if p95 else "N/A"
        print(f"{u:>4} {name:>22} {rps:>6.3f} {fail_pct:>6.1f}%  {p50_str:>6}  {p95_str:>6}")

    results.append({"users": u, **stage_data})

# ── Guardar como JSON para los gráficos ───────────────────────────────────────
out = pathlib.Path(__file__).parent / "resultados/e3b_parsed.json"
out.write_text(json.dumps(results, indent=2))
print(f"\n  → {out}")
print("\n=== Parse E3b completo ===")
