"""
Procesa e3c_stats_history.csv → métricas por nivel de carga (Poisson, 1→100 usuarios).

Ejecutar después del test:
  python load_tests/parse_e3c_results.py
"""

import csv, json, pathlib
from collections import defaultdict

HISTORY = pathlib.Path(__file__).parent / "resultados/e3c_stats_history.csv"
OUT     = pathlib.Path(__file__).parent / "resultados/e3c_parsed.json"

# Niveles objetivo (user counts estables en el CSV — coinciden con los pasos del shape)
TARGET_USERS = [1, 5, 10, 20, 30, 40, 50, 70, 100]

# ── Leer CSV (solo filas Aggregated, User Count en lista objetivo) ─────────────
rows_by_u = defaultdict(list)
with open(HISTORY) as f:
    for row in csv.DictReader(f):
        u = int(row["User Count"])
        if u in TARGET_USERS:
            rps    = float(row["Requests/s"])
            fail_s = float(row["Failures/s"])
            p50    = row["50%"]
            p95    = row["95%"]
            p99    = row["99%"]
            rows_by_u[u].append({
                "rps":    rps,
                "fail_s": fail_s,
                "p50":    float(p50) if p50 not in ("N/A", "") else None,
                "p95":    float(p95) if p95 not in ("N/A", "") else None,
                "p99":    float(p99) if p99 not in ("N/A", "") else None,
            })

# ── Calcular métricas usando la segunda mitad de cada ventana ─────────────────
results = []
print(f"\n{'u':>5}  {'TXs/s':>7}  {'trips/s':>8}  {'fail%':>6}  {'p50(ms)':>9}  {'p95(ms)':>9}")
print("-" * 60)

for u in TARGET_USERS:
    rows = rows_by_u.get(u, [])
    if not rows:
        print(f"{u:>5}  (sin datos)")
        continue
    # Usar la segunda mitad para evitar el transitorio de rampa
    half = max(1, len(rows) // 2)
    window = rows[half:]

    rps      = sum(r["rps"]    for r in window) / len(window)
    fail_s   = sum(r["fail_s"] for r in window) / len(window)
    fail_pct = (fail_s / rps * 100) if rps > 0 else 0
    trips_s  = rps / 3

    p50s = [r["p50"] for r in window if r["p50"] is not None]
    p95s = [r["p95"] for r in window if r["p95"] is not None]
    p50  = sum(p50s) / len(p50s) if p50s else None
    p95  = sum(p95s) / len(p95s) if p95s else None

    results.append({
        "users":   u,
        "rps":     round(rps, 3),
        "trips_s": round(trips_s, 3),
        "fail_pct": round(fail_pct, 1),
        "p50":     round(p50) if p50 else None,
        "p95":     round(p95) if p95 else None,
    })
    p50_s = f"{p50:.0f}" if p50 else "N/A"
    p95_s = f"{p95:.0f}" if p95 else "N/A"
    print(f"{u:>5}  {rps:>7.2f}  {trips_s:>8.3f}  {fail_pct:>5.1f}%  {p50_s:>9}  {p95_s:>9}")

OUT.write_text(json.dumps(results, indent=2))
print(f"\n  → {OUT}")
print("=== Parse E3c completado ===")
