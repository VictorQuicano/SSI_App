"""
Genera gráficos 07c-09c para el Escenario 3c (llegadas Poisson, 1→100 usuarios).
Ejecutar: python load_tests/gen_graficos_e3c.py
"""

import json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT   = pathlib.Path("load_tests/resultados")
DATA  = json.loads((OUT / "e3c_parsed.json").read_text())

users    = [d["users"]   for d in DATA]
trips_s  = [d["trips_s"] for d in DATA]
fail_pct = [d["fail_pct"] for d in DATA]
p50      = [d["p50"] or 0 for d in DATA]
p95      = [d["p95"] or 0 for d in DATA]

# Techo teórico
BLOCK_GAS  = 16_234_336
GAS_PER_TX = 400_000
BLOCK_TIME = 5.0
MAX_TPS    = (BLOCK_GAS // GAS_PER_TX) / BLOCK_TIME   # 8.0 TX/s
MAX_TRIPS  = MAX_TPS / 3                               # 2.67 trips/s

# Ideal lineal (ajustado a E3c: ciclo ~18s con exponential(3))
ideal_trips = [u * (3 / 18) for u in users]   # u * 0.167 TXs/s / 3 ops
# pero se muestra como viajes: u * 1/18
ideal_trips = [u / 18 for u in users]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.35, "figure.dpi": 150,
})

C_MAIN  = "#2563EB"
C_IDEAL = "#94A3B8"
C_CEIL  = "#DC2626"
C_E3B   = "#F97316"
C_LAT   = "#7C3AED"
C_FAIL  = "#EF4444"
C_OK    = "#16A34A"

# Separar zonas sana / saturada
users_ok   = [u for u, f in zip(users, fail_pct) if f == 0]
trips_ok   = [t for t, f in zip(trips_s, fail_pct) if f == 0]
users_sat  = [u for u, f in zip(users, fail_pct) if f > 0]
trips_sat  = [t for t, f in zip(trips_s, fail_pct) if f > 0]

# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 07c — Throughput real (Poisson) vs techo teórico
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))

ax.plot(users_ok,  trips_ok,  "o-",  color=C_OK,   linewidth=2.5, markersize=7,
        label="E3c zona lineal (0% fallos)")
ax.plot(users_sat, trips_sat, "X--", color=C_FAIL,  linewidth=2.0, markersize=9,
        label="E3c zona saturada (fallos presentes)")
ax.plot(users, ideal_trips, "--",    color=C_IDEAL, linewidth=1.4,
        label="Ideal lineal (1 viaje cada 18 s/usuario)")
ax.axhline(MAX_TRIPS, color=C_CEIL, linewidth=1.4, linestyle=":",
           label=f"Techo gas_limit: {MAX_TRIPS:.2f} trips/s (~{MAX_TRIPS*3:.1f} TXs/s)")

ax.axvspan(50, 110, alpha=0.06, color=C_FAIL, label="Zona de saturación (>50u)")

ax.annotate("Colapso: 100u\n36.6% fallos\nRPC sobrecargado",
            xy=(100, trips_sat[-1]), xytext=(72, 3.8),
            fontsize=9, color=C_FAIL,
            arrowprops=dict(arrowstyle="->", color=C_FAIL, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEE2E2", alpha=0.9))

ax.annotate("50u: 9.3 TXs/s\n(sobre techo, aún OK)",
            xy=(50, trips_ok[-1]), xytext=(25, 3.5),
            fontsize=9, color=C_OK,
            arrowprops=dict(arrowstyle="->", color=C_OK, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#DCFCE7", alpha=0.9))

ax.set_xlabel("Usuarios concurrentes")
ax.set_ylabel("Viajes completos / segundo")
ax.set_title("Escenario 3c — Throughput con llegadas Poisson (exponential(3s))")
ax.set_xticks(users)
ax.set_xlim(0, 108)
ax.set_ylim(0, 5.5)
ax.legend(loc="upper left", fontsize=8.5)

plt.tight_layout()
plt.savefig(OUT / "grafico_07c_e3c_throughput.png")
plt.close()
print("✓ grafico_07c_e3c_throughput.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 08c — Latencia: p50 vs p95 (la historia del mempool)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))

p95_s = [v / 1000 for v in p95]
p50_s = [v / 1000 for v in p50]

ax.plot(users, p50_s, "o-",  color=C_MAIN,  linewidth=2.5, markersize=7, label="p50 (mediana)")
ax.plot(users, p95_s, "s--", color=C_FAIL,  linewidth=2.0, markersize=6, label="p95")

ax.axhline(BLOCK_TIME, color=C_CEIL, linewidth=1.2, linestyle=":",
           label=f"1 bloque = {BLOCK_TIME:.0f} s (latencia mínima)")
ax.axhline(BLOCK_TIME * 5, color=C_CEIL, linewidth=0.8, linestyle="--", alpha=0.5,
           label=f"5 bloques = {BLOCK_TIME*5:.0f} s")

ax.axvspan(50, 110, alpha=0.06, color=C_FAIL)

ax.annotate("p95: 24.3s\n(~5 bloques de espera)",
            xy=(100, p95_s[-1]), xytext=(65, 22),
            fontsize=9, color=C_FAIL,
            arrowprops=dict(arrowstyle="->", color=C_FAIL, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEE2E2", alpha=0.9))

ax.annotate("p50 estable en 5s\n(TXs que caben en el bloque\nactual o el siguiente)",
            xy=(100, p50_s[-1]), xytext=(55, 10),
            fontsize=9, color=C_MAIN,
            arrowprops=dict(arrowstyle="->", color=C_MAIN, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#DBEAFE", alpha=0.9))

ax.set_xlabel("Usuarios concurrentes")
ax.set_ylabel("Latencia (segundos)")
ax.set_title("Escenario 3c — Latencia p50 vs p95: bifurcación bajo saturación del mempool")
ax.set_xticks(users)
ax.set_xlim(0, 108)
ax.set_ylim(0, 30)
ax.legend(loc="upper left", fontsize=9)

plt.tight_layout()
plt.savefig(OUT / "grafico_08c_e3c_latencia.png")
plt.close()
print("✓ grafico_08c_e3c_latencia.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 09c — Tasa de fallos + desglose de tipos
# ─────────────────────────────────────────────────────────────────────────────
# Datos de error report (de la salida final de Locust)
err_revert_cr = 592    # createReservation tx reverted
err_conn      = 282    # ConnectionError (Remote end closed)
err_start     = 18     # startTrip tx reverted
total_reqs    = 12139

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# Panel izquierdo: tasa de fallos por nivel
colors_bar = [C_OK if f == 0 else C_FAIL for f in fail_pct]
bars = ax1.bar(users, fail_pct, color=colors_bar, alpha=0.85, width=3.5)
for bar, f in zip(bars, fail_pct):
    if f > 0:
        ax1.text(bar.get_x() + bar.get_width()/2, f + 0.5,
                 f"{f:.1f}%", ha="center", va="bottom",
                 fontsize=9, color=C_FAIL, fontweight="bold")

ax1.axvline(48, color=C_CEIL, linewidth=1.2, linestyle="--", alpha=0.7,
            label="Techo teórico: ~48u")
ax1.set_xlabel("Usuarios concurrentes")
ax1.set_ylabel("Tasa de fallos (%)")
ax1.set_title("Tasa de fallos por nivel de carga")
ax1.set_xticks(users)
ax1.set_ylim(0, 45)
ax1.legend(fontsize=9)

green_patch = mpatches.Patch(color=C_OK, alpha=0.85, label="Sin fallos")
red_patch   = mpatches.Patch(color=C_FAIL, alpha=0.85, label="Fallos presentes")
ax1.legend(handles=[green_patch, red_patch,
                    mpatches.Patch(color=C_CEIL, label="Techo teórico ~48u")],
           fontsize=8.5)

# Panel derecho: desglose de tipos de error (total del test)
labels = [
    f"createReservation\nrevertida\n({err_revert_cr} TXs)",
    f"Error conexión RPC\n(Besu saturado)\n({err_conn} TXs)",
    f"startTrip\nrevertida\n({err_start} TXs)",
]
sizes  = [err_revert_cr, err_conn, err_start]
colors_pie = ["#F97316", "#EF4444", "#FBBF24"]
explode    = [0.04, 0.04, 0.04]

wedges, texts, autotexts = ax2.pie(
    sizes, labels=labels, colors=colors_pie,
    autopct="%1.1f%%", explode=explode,
    textprops={"fontsize": 8.5},
    pctdistance=0.75,
)
for at in autotexts:
    at.set_fontweight("bold")

ax2.set_title(f"Desglose de los 892 fallos (de {total_reqs} TXs totales)")

fig.suptitle("Escenario 3c — Fallos bajo saturación (Poisson, 1→100u)",
             fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(OUT / "grafico_09c_e3c_fallos.png")
plt.close()
print("✓ grafico_09c_e3c_fallos.png")

print("\n=== Gráficos E3c generados ===")
