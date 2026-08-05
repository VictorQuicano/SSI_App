"""
Genera graficos 07-09 del Escenario 3 (Throughput Besu).

Ejecutar:
  cd SSI_App
  source venv/bin/activate
  python load_tests/gen_graficos_e3.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT = "load_tests/resultados"

# ── Datos extraidos del batch E3 ──────────────────────────────────────────────
users = [1, 3, 5, 7, 10]

# Throughput en r/s
cr_total_rps   = [0.07, 0.34, 0.61, 0.74, 0.94]   # createReservation (todos los intentos)
cr_fail_pct    = [0.00, 0.60, 0.664, 0.545, 0.429] # tasa de fallo
cr_success_rps = [r*(1-f) for r, f in zip(cr_total_rps, cr_fail_pct)]  # ≈ startTrip
start_rps      = [0.07, 0.14, 0.21, 0.33, 0.53]
complete_rps   = [0.07, 0.13, 0.19, 0.33, 0.51]

# Latencia de u=1 (baseline limpio, 0 fallos)
ops_labels = ["createReservation", "startTrip", "completeTrip"]
p50 = [3700, 5000, 5000]
p95 = [3900, 5000, 5100]
p99 = [3900, 5000, 5100]

# Fallos de createReservation
fail_pct_pct = [f*100 for f in cr_fail_pct]

# ── Estilos globales ──────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":    "DejaVu Sans",
    "font.size":      11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":      True,
    "grid.alpha":     0.35,
    "figure.dpi":     150,
})

C_CREATE   = "#2563EB"  # azul
C_START    = "#16A34A"  # verde
C_COMPLETE = "#9333EA"  # violeta
C_FAIL     = "#DC2626"  # rojo
C_IDEAL    = "#94A3B8"  # gris suave
C_ANNOT    = "#B45309"  # ámbar oscuro

# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 07 — Throughput por operación
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))

# createReservation: intentos totales (línea discontinua)
ax.plot(users, cr_total_rps, "o--", color=C_CREATE, linewidth=1.5,
        alpha=0.5, label="createReservation (intentos totales)")
# createReservation exitosos ≈ startTrip
ax.plot(users, cr_success_rps, "o-", color=C_CREATE, linewidth=2.0,
        label="createReservation (exitosos)")
ax.plot(users, start_rps,      "s-", color=C_START,    linewidth=2.0,
        label="startTrip")
ax.plot(users, complete_rps,   "^-", color=C_COMPLETE, linewidth=2.0,
        label="completeTrip")

# Línea ideal (escalado lineal desde u=1)
ideal = [0.07 * u for u in users]
ax.plot(users, ideal, "--", color=C_IDEAL, linewidth=1.2,
        label="Escalado lineal ideal")

# Anotación: cuello de botella
ax.annotate(
    "Cuello de botella:\nnonce serializado\n(1 TX/vez)",
    xy=(10, complete_rps[-1]), xytext=(7.2, 0.62),
    fontsize=9, color=C_ANNOT,
    arrowprops=dict(arrowstyle="->", color=C_ANNOT, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEF3C7", alpha=0.85),
)

ax.set_xlabel("Usuarios concurrentes")
ax.set_ylabel("Throughput (transacciones / segundo)")
ax.set_title("Escenario 3 — Throughput de operaciones Besu (QBFT)")
ax.set_xticks(users)
ax.legend(loc="upper left", fontsize=9)
ax.set_ylim(0, 1.0)

plt.tight_layout()
plt.savefig(f"{OUT}/grafico_07_besu_throughput.png")
plt.close()
print("✓ grafico_07_besu_throughput.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 08 — Latencia por operación (baseline u=1, 0% fallos)
# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 5))

x     = np.arange(len(ops_labels))
width = 0.25
colors_ops = [C_CREATE, C_START, C_COMPLETE]

bars_p50 = ax.bar(x - width, p50, width, label="p50", color=colors_ops, alpha=0.85)
bars_p95 = ax.bar(x,         p95, width, label="p95", color=colors_ops, alpha=0.60)
bars_p99 = ax.bar(x + width, p99, width, label="p99", color=colors_ops, alpha=0.35)

# Etiquetas de valor
for bars in [bars_p50, bars_p95, bars_p99]:
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 40,
                f"{int(h/1000.0):.1f}s", ha="center", va="bottom", fontsize=8)

# Leyenda de percentiles
p50_patch = mpatches.Patch(facecolor="grey", alpha=0.85, label="p50")
p95_patch = mpatches.Patch(facecolor="grey", alpha=0.60, label="p95")
p99_patch = mpatches.Patch(facecolor="grey", alpha=0.35, label="p99")
ax.legend(handles=[p50_patch, p95_patch, p99_patch], loc="upper right")

# Anotación de bloque QBFT
ax.annotate(
    "~1 ciclo de bloque\nQBFT ≈ 3–5 s",
    xy=(0, 3700), xytext=(0.8, 4400),
    fontsize=9, color=C_ANNOT,
    arrowprops=dict(arrowstyle="->", color=C_ANNOT, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEF3C7", alpha=0.85),
)

ax.set_xticks(x)
ax.set_xticklabels(ops_labels)
ax.set_ylabel("Latencia (ms)")
ax.set_title("Escenario 3 — Latencia por operación (u=1, línea de base limpia)")
ax.set_ylim(0, 6500)

plt.tight_layout()
plt.savefig(f"{OUT}/grafico_08_besu_latencia.png")
plt.close()
print("✓ grafico_08_besu_latencia.png")


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICO 09 — Análisis de fallos de createReservation
# ─────────────────────────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Panel izquierdo: tasa de fallo
ax1.bar(users, fail_pct_pct, color=C_FAIL, alpha=0.75, width=1.5)
ax1.axhline(0, color=C_FAIL, linewidth=0.8, linestyle="--", alpha=0.3)

# Anotación
ax1.annotate(
    "u=1: 0% fallos\n(eVTOLs limpios)",
    xy=(1, 0), xytext=(2.5, 15),
    fontsize=9, color="#166534",
    arrowprops=dict(arrowstyle="->", color="#166534", lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#DCFCE7", alpha=0.9),
)
ax1.annotate(
    "u=3–10: 43–66%\nartefacto del batch\n(eVTOLs bloqueados)",
    xy=(5, 66.4), xytext=(6.2, 68),
    fontsize=9, color=C_FAIL,
    arrowprops=dict(arrowstyle="->", color=C_FAIL, lw=1.2),
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#FEE2E2", alpha=0.9),
)

ax1.set_xlabel("Usuarios concurrentes")
ax1.set_ylabel("Tasa de fallos (%)")
ax1.set_title("Tasa de fallos de createReservation")
ax1.set_xticks(users)
ax1.set_ylim(0, 80)

# Panel derecho: eVTOLs bloqueados estimados al inicio de cada sub-test
# u=1: 0 bloqueados; u=3: 1 (de u=1); u=5: ~4; u=7: ~6; u=10: ~5
evtols_stuck = [0, 1, 4, 6, 5]  # estimados por inspección on-chain post-batch

bar_colors = [C_START if s == 0 else C_FAIL for s in evtols_stuck]
ax2.bar(users, evtols_stuck, color=bar_colors, alpha=0.75, width=1.5)

# Etiquetas de valor
for u_val, s in zip(users, evtols_stuck):
    ax2.text(u_val, s + 0.1, str(s), ha="center", va="bottom", fontsize=10, fontweight="bold")

ax2.set_xlabel("Usuarios concurrentes en sub-test")
ax2.set_ylabel("eVTOLs bloqueados al inicio")
ax2.set_title("eVTOLs en estado no-PARKED al inicio de cada sub-test")
ax2.set_xticks(users)
ax2.set_ylim(0, 8)

clean_patch  = mpatches.Patch(facecolor=C_START, alpha=0.75, label="0 bloqueados (limpio)")
stuck_patch  = mpatches.Patch(facecolor=C_FAIL,  alpha=0.75, label="≥1 bloqueado (contaminado)")
ax2.legend(handles=[clean_patch, stuck_patch], loc="upper right", fontsize=9)

fig.suptitle("Escenario 3 — Análisis de fallos: artefacto del batch vs. comportamiento real",
             fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(f"{OUT}/grafico_09_besu_fallos.png")
plt.close()
print("✓ grafico_09_besu_fallos.png")

print("\n=== Gráficos E3 generados ===")
