"""
Genera gráficos 07b-09b para el Escenario 3b (stepped load limpio).
Ejecutar: python load_tests/gen_graficos_e3b.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = "load_tests/resultados"

# ── Datos E3b (stepped load, 0% fallos) ──────────────────────────────────────
users       = [1, 3, 5, 10, 15, 20, 30]
rps_total   = [0.200, 0.600, 1.000, 2.000, 3.000, 4.000, 6.000]
trips_s     = [r/3 for r in rps_total]   # ciclos completos/s
p50_all     = [5000, 5000, 5000, 5000, 5000, 5000, 5000]
p95_all     = [5100, 5100, 5100, 5100, 5100, 5100, 5100]

# Techo teórico: gas_limit=16234336, gas_per_tx=400000, block_time=5s
BLOCK_GAS   = 16_234_336
GAS_PER_TX  = 400_000
BLOCK_TIME  = 5.0
MAX_TPS     = (BLOCK_GAS // GAS_PER_TX) / BLOCK_TIME   # 8.0 TX/s
MAX_TRIPS   = MAX_TPS / 3                               # 2.67 trips/s
CEILING_U   = MAX_TRIPS / 0.0667                        # ~40 users

# Ideal lineal desde u=1
ideal_trips = [0.0667 * u for u in users]

# E3 original (contaminado) para comparativa
e3_users    = [1, 3, 5, 7, 10]
e3_complete = [0.07, 0.13, 0.19, 0.33, 0.51]   # completeTrip rps (único sin fallo)
e3_cr_fail  = [0,    60,   66.4, 54.5, 42.9]    # % fallo createReservation

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.35, "figure.dpi": 150,
})

C_MAIN  = "#2563EB"
C_IDEAL = "#94A3B8"
C_CEIL  = "#DC2626"
C_E3    = "#F97316"
C_LAT   = "#7C3AED"
C_ANNOT = "#B45309"

# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 07b — Throughput escalado linealmente
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))

ax.plot(users, trips_s, "o-", color=C_MAIN, linewidth=2.5,
        markersize=7, label="E3b: trips completados/s (0% fallos)")
ax.plot(users, ideal_trips, "--", color=C_IDEAL, linewidth=1.5,
        label="Escalado lineal ideal (0.067 trips/s por usuario)")

# Techo teórico
u_ceil_x = np.linspace(0, 55, 100)
ax.axhline(MAX_TRIPS, color=C_CEIL, linewidth=1.4, linestyle=":",
           label=f"Techo teórico: {MAX_TRIPS:.1f} trips/s\n(gas_limit={BLOCK_GAS//10**6:.0f}M / {GAS_PER_TX//1000}k gas/TX / {BLOCK_TIME:.0f}s bloque)")

ax.annotate(
    f"Proyección: techo a ~{CEILING_U:.0f} usuarios",
    xy=(CEILING_U, MAX_TRIPS), xytext=(22, MAX_TRIPS*0.6),
    fontsize=9, color=C_CEIL,
    arrowprops=dict(arrowstyle="->", color=C_CEIL, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEE2E2", alpha=0.85),
)

ax.annotate(
    "Escalado ~lineal\nhasta 30u",
    xy=(30, trips_s[-1]), xytext=(18, 1.8),
    fontsize=9, color=C_MAIN,
    arrowprops=dict(arrowstyle="->", color=C_MAIN, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#DBEAFE", alpha=0.85),
)

ax.set_xlabel("Usuarios concurrentes")
ax.set_ylabel("Viajes completos / segundo")
ax.set_title("Escenario 3b — Throughput Besu (QBFT, stepped load, 0% fallos)")
ax.set_xticks(users)
ax.set_xlim(0, 35)
ax.set_ylim(0, 3.5)
ax.legend(loc="upper left", fontsize=9)

plt.tight_layout()
plt.savefig(f"{OUT}/grafico_07b_besu_throughput_limpio.png")
plt.close()
print("✓ grafico_07b_besu_throughput_limpio.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 08b — Latencia plana (la clave de Besu vs ACA-Py)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))

ax.plot(users, p50_all, "o-", color=C_MAIN, linewidth=2.5,
        markersize=7, label="p50 (Besu QBFT)")
ax.plot(users, p95_all, "s--", color=C_LAT, linewidth=2.0,
        markersize=6, label="p95 (Besu QBFT)")

# Referencia: latencia esperada si hubiera cuello de botella serial (Ley de Little)
# λ = MAX_TPS/3 trips/s; latencia = N/λ
little_lat = [u / (MAX_TRIPS) * 5000 for u in users]  # en ms, normalizado
ax.plot(users, little_lat, "--", color=C_E3, linewidth=1.5, alpha=0.7,
        label="Si hubiera cola serial (Ley de Little × factor)")

ax.annotate(
    "Latencia PLANA: cada TX\nse mina en el mismo bloque\nindependiente de la carga",
    xy=(15, 5000), xytext=(5, 6500),
    fontsize=9, color=C_MAIN,
    arrowprops=dict(arrowstyle="->", color=C_MAIN, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#DBEAFE", alpha=0.85),
)

ax.set_xlabel("Usuarios concurrentes")
ax.set_ylabel("Latencia (ms)")
ax.set_title("Escenario 3b — Latencia por TX (tiempo de bloque QBFT, no crece con carga)")
ax.set_xticks(users)
ax.set_ylim(0, 10000)
ax.legend(loc="upper right", fontsize=9)

# Anotación de contraste con E2
ax.text(0.97, 0.12,
        "Contraste con E2 (ACA-Py):\nlatencia en E2 crece linealmente\npor procesamiento serial (CL).\nBesu procesa en paralelo por bloque.",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#F5F3FF", alpha=0.9))

plt.tight_layout()
plt.savefig(f"{OUT}/grafico_08b_besu_latencia_plana.png")
plt.close()
print("✓ grafico_08b_besu_latencia_plana.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 09b — Comparativa E3 (artefacto) vs E3b (limpio)
# ─────────────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Panel izquierdo: throughput E3 vs E3b
ax1.plot(e3_users,  e3_complete, "o--", color=C_E3,  linewidth=2.0,
         markersize=6, label="E3 (batch con artefacto): completeTrip r/s")
ax1.plot(users, trips_s, "o-", color=C_MAIN, linewidth=2.5,
         markersize=7, label="E3b (stepped limpio): trips/s")
ax1.plot(users, ideal_trips, "--", color=C_IDEAL, linewidth=1.2,
         label="Ideal lineal")

ax1.set_xlabel("Usuarios concurrentes")
ax1.set_ylabel("Viajes completos / segundo")
ax1.set_title("Throughput: E3 original vs E3b limpio")
ax1.legend(loc="upper left", fontsize=8.5)
ax1.set_xticks([1, 3, 5, 7, 10, 15, 20, 30])

# Panel derecho: tasa de fallos E3 vs E3b
ax2.bar([u-0.35 for u in e3_users], e3_cr_fail, 0.6, color=C_E3, alpha=0.8,
        label="E3: createReservation fallo %")
ax2.bar([u+0.35 for u in users[:5]], [0]*5, 0.6, color=C_MAIN, alpha=0.8,
        label="E3b: fallo % (0% en todos)")

# etiquetas sobre barras
for u_val, f in zip(e3_users, e3_cr_fail):
    ax2.text(u_val-0.35, f+1, f"{f:.0f}%", ha="center", va="bottom",
             fontsize=8.5, color=C_E3, fontweight="bold")

ax2.set_xlabel("Usuarios concurrentes")
ax2.set_ylabel("Tasa de fallos de createReservation (%)")
ax2.set_title("Fallos: E3 original (artefacto) vs E3b (limpio)")
ax2.legend(loc="upper right", fontsize=8.5)
ax2.set_ylim(0, 80)

ax2.text(5, 35,
         "E3b: 0% fallos\nen todos los\nniveles",
         ha="center", fontsize=10, color=C_MAIN, fontweight="bold",
         bbox=dict(boxstyle="round,pad=0.4", facecolor="#DBEAFE", alpha=0.9))

fig.suptitle("Escenario 3: Batch con artefacto vs Stepped load limpio",
             fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/grafico_09b_besu_comparativa.png")
plt.close()
print("✓ grafico_09b_besu_comparativa.png")

print("\n=== Gráficos E3b generados ===")
