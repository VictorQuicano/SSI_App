"""
Genera los 9 graficos de pruebas de carga del sistema TI3.
Ejecutar: python load_tests/generar_graficos.py
Salida:   load_tests/resultados/grafico_01..09_*.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.transforms as transforms
import os

OUT = os.path.join(os.path.dirname(__file__), "resultados")
os.makedirs(OUT, exist_ok=True)

# ─── Colores ────────────────────────────────────────────────────────────────
BLUE   = "#2563eb"
ORANGE = "#d97706"
GREEN  = "#16a34a"
RED    = "#dc2626"
YELLOW = "#ca8a04"
GRAY   = "#8c8fa0"

ZONE_RED_BG = (0.86, 0.20, 0.20, 0.07)
ZONE_RED_LN = (0.86, 0.20, 0.20, 0.40)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def new_fig():
    """Figura estándar con estilo limpio."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.subplots_adjust(bottom=0.28)   # espacio para zona labels + xlabel
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#dde1ea")
    ax.spines["bottom"].set_color("#dde1ea")
    ax.tick_params(colors=GRAY, labelsize=9)
    ax.grid(axis="y", color="#e4e8f0", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    return fig, ax


def add_zone(ax, x_break, x_max, lbl_ok="zona estable",
             lbl_bad="zona de colapso"):
    """
    Franja roja en la zona de colapso + línea de corte.
    Las etiquetas se ponen DEBAJO del eje X para evitar solapamientos.
    """
    ax.axvspan(x_break, x_max, color=ZONE_RED_BG, zorder=1)
    ax.axvline(x_break, color=ZONE_RED_LN, lw=1.2,
               linestyle=(0, (5, 4)), zorder=2)

    # Transformación: X en coordenadas de datos, Y en fracción del eje (0=fondo, 1=tope)
    trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
    x_ok  = (ax.get_xlim()[0] + x_break) / 2       # centro de la zona estable
    x_bad = (x_break + x_max) / 2                   # centro de la zona de colapso
    kw = dict(transform=trans, fontsize=8, color=GRAY,
              ha="center", va="top", clip_on=False)
    ax.text(x_ok,  -0.26, lbl_ok,  **kw)
    ax.text(x_bad, -0.26, lbl_bad, **kw)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=150,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {name}")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 1 — Django / registro de usuarios  [PostgreSQL 16]
# ═══════════════════════════════════════════════════════════════════════════
U1     = [10,    25,    50,    75,    100,   150,   200]
RPS1   = [8.20,  19.67, 30.15, 30.82, 30.77, 34.65, 38.77]
LAT1_S = [0.207, 0.271, 0.596, 1.244, 1.879, 2.484, 3.058]
FAIL1  = [0.0,   0.0,   0.0,   0.0,   0.0,   25.42, 41.54]
BRK1   = 130
XMAX1  = 215

# ── G01: Throughput ─────────────────────────────────────────────────────
fig, ax = new_fig()
ax.set_title("Throughput — Registro de usuarios (Django + PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ideal = [RPS1[0] * u / U1[0] for u in U1]
ax.plot(U1, ideal, color=BLUE, lw=1, ls=(0,(5,4)), alpha=0.30, label="ideal lineal")
ax.fill_between(U1, RPS1, alpha=0.10, color=BLUE)
ax.plot(U1, RPS1, color=BLUE, lw=2.2, label="throughput real")
ax.scatter(U1, RPS1, color=BLUE, s=42, zorder=5, edgecolors="white", lw=1.5)
ax.annotate("estable 30.8 r/s\n(10–100 u)", xy=(100, 30.77), xytext=(70, 38),
            fontsize=8, color=BLUE, ha="center",
            arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.7))
ax.set_xlim(0, XMAX1); ax.set_ylim(0, 46)
ax.set_xticks(U1)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Peticiones / segundo", fontsize=9)
ax.legend(fontsize=8.5, framealpha=0, loc="upper left")
add_zone(ax, BRK1, XMAX1)
save(fig, "grafico_01_throughput.png")

# ── G02: Latencia ────────────────────────────────────────────────────────
fig, ax = new_fig()
ax.set_title("Latencia p50 — Registro de usuarios (Django + PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ax.fill_between(U1, LAT1_S, alpha=0.10, color=ORANGE)
ax.plot(U1, LAT1_S, color=ORANGE, lw=2.2)
ax.scatter(U1, LAT1_S, color=ORANGE, s=42, zorder=5, edgecolors="white", lw=1.5)
for xu, yu, lbl in [(150, LAT1_S[5], "2.5 s"), (200, LAT1_S[6], "3.1 s")]:
    ax.annotate(lbl, xy=(xu, yu), xytext=(xu-28, yu+0.2),
                fontsize=8.5, color=ORANGE, ha="left")
ax.set_xlim(0, XMAX1); ax.set_ylim(0, 3.8)
ax.set_xticks(U1)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Tiempo de respuesta (s)", fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}s"))
add_zone(ax, BRK1, XMAX1)
save(fig, "grafico_02_latencia.png")

# ── G03: Fallos ──────────────────────────────────────────────────────────
COLORS1 = [GREEN, GREEN, GREEN, GREEN, GREEN, RED, RED]
fig, ax = new_fig()
ax.set_title("Tasa de fallos — Registro de usuarios (PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
bars = ax.bar(U1, FAIL1, width=12, color=COLORS1,
              zorder=3, edgecolor="white", lw=1.2)
for bar, val, col in zip(bars, FAIL1, COLORS1):
    h = bar.get_height()
    if val == 0.0:
        continue
    lbl = f"{val:.1f}%"
    if h > 12:
        ax.text(bar.get_x()+bar.get_width()/2, h/2,
                lbl, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=6)
    else:
        ax.text(bar.get_x()+bar.get_width()/2, h+0.8,
                lbl, ha="center", va="bottom",
                fontsize=8.5, fontweight="bold", color=col, zorder=6)
ax.set_xlim(0, XMAX1); ax.set_ylim(0, 57)
ax.set_xticks(U1)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Tasa de fallos (%)", fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
legend_patches = [
    mpatches.Patch(color=GREEN, label="Estable (0 %)"),
    mpatches.Patch(color=RED,   label="Colapso (>=25 %)"),
]
ax.legend(handles=legend_patches, fontsize=8.5, framealpha=0, loc="upper left")
add_zone(ax, BRK1, XMAX1)
save(fig, "grafico_03_fallos.png")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 2 — ACA-Py / emisión de credenciales SSI  [PostgreSQL 16]
# ═══════════════════════════════════════════════════════════════════════════
U2    = [1,    3,    5,    10,   15,   25,   30,   40,   50]
RPS2  = [0.98, 2.95, 4.91, 9.74, 14.53,23.04,24.19,22.38,23.25]
P50_2 = [40,   48,   47,   44,   47,   90,   190,  560,  470]   # ms
P99_2 = [320,  190,  200,  310,  400,  530,  1500, 1600, 1700]  # ms
FAIL2 = [0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.07, 0.45, 1.22]
BRK2  = 28
XMAX2 = 55

# ── G04: Throughput ──────────────────────────────────────────────────────
fig, ax = new_fig()
ax.set_title("Throughput — Emision de credenciales SSI (ACA-Py + PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ideal2 = [RPS2[0]*u/U2[0] for u in U2]
ax.plot(U2, ideal2, color=BLUE, lw=1, ls=(0,(5,4)), alpha=0.30, label="ideal lineal")
ax.fill_between(U2, RPS2, alpha=0.10, color=BLUE)
ax.plot(U2, RPS2, color=BLUE, lw=2.2, label="throughput real")
ax.scatter(U2, RPS2, color=BLUE, s=42, zorder=5, edgecolors="white", lw=1.5)
ax.annotate("pico 24.2 r/s", xy=(30, 24.19), xytext=(36, 27),
            fontsize=8, color=BLUE, ha="center",
            arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.7))
ax.set_xlim(0, XMAX2); ax.set_ylim(0, 32)
ax.set_xticks(U2)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Peticiones / segundo", fontsize=9)
ax.legend(fontsize=8.5, framealpha=0, loc="upper left")
add_zone(ax, BRK2, XMAX2, lbl_bad="zona degradada")
save(fig, "grafico_04_emision_throughput.png")

# ── G05: Latencia p50 / p99 ──────────────────────────────────────────────
CAP = 1700
p99_s = [min(v, CAP)/1000 for v in P99_2]
p50_s = [v/1000 for v in P50_2]

fig, ax = new_fig()
ax.set_title("Latencia p50 / p99 — Emision de credenciales SSI (ACA-Py + PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ax.fill_between(U2, p99_s, alpha=0.08, color=ORANGE)
ax.plot(U2, p99_s, color=ORANGE, lw=2.2, label="p99")
ax.scatter(U2, p99_s, color=ORANGE, s=42, zorder=5, edgecolors="white", lw=1.5)
ax.fill_between(U2, p50_s, alpha=0.12, color=BLUE)
ax.plot(U2, p50_s, color=BLUE, lw=2.2, label="p50")
ax.scatter(U2, p50_s, color=BLUE, s=42, zorder=5, edgecolors="white", lw=1.5)
for xu, vr, ys in zip(U2, P99_2, p99_s):
    if vr >= 400:
        ax.text(xu, ys+0.05, f"{vr} ms",
                ha="center", va="bottom", fontsize=7.5, color=ORANGE)
ax.set_xlim(0, XMAX2); ax.set_ylim(0, 2.0)
ax.set_xticks(U2)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Latencia (s)", fontsize=9)
ax.legend(fontsize=8.5, framealpha=0, loc="upper left")
add_zone(ax, BRK2, XMAX2, lbl_bad="zona degradada")
save(fig, "grafico_05_emision_latencia.png")

# ── G06: Fallos ──────────────────────────────────────────────────────────
COLORS2 = [GREEN]*6 + [GREEN, YELLOW, YELLOW]
fig, ax = new_fig()
ax.set_title("Tasa de fallos — Emision de credenciales SSI (PostgreSQL)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
bars = ax.bar(U2, FAIL2, width=3.5, color=COLORS2,
              zorder=3, edgecolor="white", lw=1.2)
for bar, val, col in zip(bars, FAIL2, COLORS2):
    h = bar.get_height()
    if val == 0.0:
        continue
    lbl = f"{val:.2f}%"
    ax.text(bar.get_x()+bar.get_width()/2, h+0.03,
            lbl, ha="center", va="bottom",
            fontsize=9, fontweight="bold", color=col, zorder=6)
ax.set_xlim(0, XMAX2); ax.set_ylim(0, 2.5)
ax.set_xticks(U2)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Tasa de fallos (%)", fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1f}%"))
legend_p2 = [
    mpatches.Patch(color=GREEN,  label="Estable (0 %)"),
    mpatches.Patch(color=YELLOW, label="Degradado (<2 %)"),
]
ax.legend(handles=legend_p2, fontsize=8.5, framealpha=0, loc="upper left")
add_zone(ax, BRK2, XMAX2, lbl_bad="zona degradada")
save(fig, "grafico_06_emision_fallos.png")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 3 — Besu / reservas de vuelo
# ═══════════════════════════════════════════════════════════════════════════
U3     = [1,    3,     5,     10]
TRIPS3 = [6.0,  1.0,   1.0,   0.0]
FAIL3  = [0.0,  87.88, 95.56, 99.99]
AVG3_S = [5.0,  4.61,  4.967, 0.042]
P50_3  = [5.0,  5.0,   5.0,   0.042]
BRK3   = 2.0
XMAX3  = 12

# ── G07: Throughput ──────────────────────────────────────────────────────
fig, ax = new_fig()
ax.set_title("Throughput — Reservas de vuelo en Besu  (1 EVTOL disponible)",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ax.fill_between(U3, TRIPS3, alpha=0.12, color=BLUE)
ax.plot(U3, TRIPS3, color=BLUE, lw=2.2)
ax.scatter(U3, TRIPS3, color=BLUE, s=50, zorder=5, edgecolors="white", lw=2)
for xu, yu in zip(U3, TRIPS3):
    if yu > 0:
        ax.text(xu, yu+0.35, f"{yu:.0f}",
                ha="center", va="bottom", fontsize=11, fontweight="bold", color=BLUE)
    else:
        # 0 a la derecha del punto para no tapar el tick del eje X
        ax.text(xu+0.4, yu+0.35, "0",
                ha="left", va="bottom", fontsize=11, fontweight="bold", color=BLUE)
ax.set_xlim(0, XMAX3); ax.set_ylim(0, 8)
ax.set_xticks(U3)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Viajes completos en 90 s", fontsize=9)
add_zone(ax, BRK3, XMAX3, lbl_bad="congestion / colapso")
save(fig, "grafico_07_besu_throughput.png")

# ── G08: Fallos ──────────────────────────────────────────────────────────
COLORS3 = [GREEN, RED, RED, RED]
fig, ax = new_fig()
ax.set_title("Tasa de fallos — Reservas en Besu",
             fontsize=11, fontweight="bold", loc="left", pad=10)
bars = ax.bar(U3, FAIL3, width=1.3, color=COLORS3,
              zorder=3, edgecolor="white", lw=1.2)
for bar, val, col in zip(bars, FAIL3, COLORS3):
    h = bar.get_height()
    if val == 0.0:
        continue
    lbl = f"{val:.1f}%"
    if h > 15:
        ax.text(bar.get_x()+bar.get_width()/2, h/2,
                lbl, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="white", zorder=6)
    else:
        ax.text(bar.get_x()+bar.get_width()/2, h+1,
                lbl, ha="center", va="bottom",
                fontsize=9.5, fontweight="bold", color=col, zorder=6)
ax.set_xlim(0, XMAX3); ax.set_ylim(0, 112)
ax.set_xticks(U3)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Tasa de fallos (%)", fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
legend_p3 = [
    mpatches.Patch(color=GREEN, label="Estable (0 %)"),
    mpatches.Patch(color=RED,   label="Colapso (>=88 %)"),
]
ax.legend(handles=legend_p3, fontsize=8.5, framealpha=0, loc="upper right")
add_zone(ax, BRK3, XMAX3, lbl_bad="colapso")
save(fig, "grafico_08_besu_fallos.png")

# ── G09: Latencia ────────────────────────────────────────────────────────
fig, ax = new_fig()
ax.set_title("Latencia — Reservas en Besu",
             fontsize=11, fontweight="bold", loc="left", pad=10)
ax.fill_between(U3, AVG3_S, alpha=0.08, color=ORANGE)
ax.plot(U3, AVG3_S, color=ORANGE, lw=2.2, label="Promedio")
ax.scatter(U3, AVG3_S, color=ORANGE, s=44, zorder=5, edgecolors="white", lw=1.8)
ax.fill_between(U3, P50_3, alpha=0.12, color=BLUE)
ax.plot(U3, P50_3, color=BLUE, lw=2.2, label="p50")
ax.scatter(U3, P50_3, color=BLUE, s=44, zorder=5, edgecolors="white", lw=1.8)
# anotacion del punto 10u (arriba y a la izquierda del punto, zona despejada)
ax.text(9.5, 1.2, "10u: rechazo RPC\n(nonce too distant)\n~42 ms",
        ha="right", va="bottom", fontsize=7.5, color=GRAY)
# leyenda arriba-derecha (los datos altos estan a la izquierda)
ax.legend(fontsize=8.5, framealpha=0, loc="upper right")
ax.set_xlim(0, XMAX3); ax.set_ylim(0, 6.2)
ax.set_xticks(U3)
ax.set_xlabel("Usuarios concurrentes", fontsize=9, labelpad=6)
ax.set_ylabel("Latencia de createReservation (s)", fontsize=9)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}s"))
add_zone(ax, BRK3, XMAX3,
         lbl_ok="on-chain (~5 s/bloque)",
         lbl_bad="rechazo RPC (~42 ms)")
save(fig, "grafico_09_besu_latencia.png")

print("\nTodos los graficos generados en:", OUT)
