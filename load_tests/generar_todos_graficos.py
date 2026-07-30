"""
Regenera los 9 gráficos de pruebas de carga con layout limpio.
Correcciones respecto a la versión anterior:
  - Etiquetas de zona al fondo (no solapan leyenda ni datos)
  - Leyendas en esquinas que no conflictúan con ninguna etiqueta
  - Títulos cortos + anotación de contexto separada
  - Figura más ancha (9×4.5) para dar respiración
  - Anotaciones de puntos clave bien posicionadas
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np

OUT = "/home/egrm23/Documentos/TI3/SSI_App/load_tests/resultados/"

# ── Paleta ───────────────────────────────────────────────────────────────────
C = {
    "card":    "#ffffff",
    "ink":     "#0f1217",
    "ink2":    "#52555f",
    "ink3":    "#9399a6",
    "grid":    "#e4e8f0",
    "blue":    "#2563eb",
    "orange":  "#d97706",
    "green":   "#16a34a",
    "red":     "#dc2626",
    "yellow":  "#ca8a04",
    "salmon":  "#e07050",
    "zone_bad_bg":  (0.86, 0.20, 0.20, 0.055),
    "zone_bad_ln":  (0.86, 0.20, 0.20, 0.35),
    "zone_ok_bg":   (0.09, 0.64, 0.29, 0.06),
}

FIG_W, FIG_H = 9.0, 4.5

def fig_ax():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.patch.set_facecolor(C["card"])
    ax.set_facecolor(C["card"])
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(C["grid"])
    ax.tick_params(colors=C["ink3"], labelsize=9)
    ax.grid(axis="y", color=C["grid"], linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    return fig, ax

def label_ax(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontsize=9.5, labelpad=6, color=C["ink2"])
    ax.set_ylabel(ylabel, fontsize=9.5, labelpad=6, color=C["ink2"])

def title_ax(ax, title, subtitle=None):
    ax.set_title(title, fontsize=11.5, fontweight="bold", color=C["ink"],
                 pad=8, loc="left")
    if subtitle:
        ax.annotate(subtitle, xy=(0, 1.01), xycoords="axes fraction",
                    fontsize=8, color=C["ink3"], ha="left", va="bottom")

def zone_split(ax, x_break, xmax, ymax, label_ok="zona estable",
               label_bad="zona de colapso"):
    """Dibuja la división de zonas y pone etiquetas al FONDO del gráfico."""
    ax.axvspan(x_break, xmax, color=C["zone_bad_bg"], zorder=1)
    ax.axvline(x_break, color=C["zone_bad_ln"], lw=1.1,
               linestyle=(0, (5, 4)), zorder=2)
    y_lbl = ymax * 0.04
    ax.text(x_break + (xmax - x_break) * 0.05, y_lbl, label_bad,
            fontsize=7.5, color=C["ink3"], va="bottom", ha="left")
    ax.text(x_break * 0.05, y_lbl, label_ok,
            fontsize=7.5, color=C["ink3"], va="bottom", ha="left")

def save(fig, fname):
    plt.tight_layout(pad=1.4)
    fig.savefig(OUT + fname, dpi=155, bbox_inches="tight",
                facecolor=C["card"])
    plt.close(fig)
    print(f"✅  {fname}")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 1 — Registro de usuarios en Django
# ═══════════════════════════════════════════════════════════════════════════

S1_USERS = [10, 25, 50, 75, 100, 150, 200]
S1_RPS   = [8.0, 17.7, 31.9, 29.5, 28.2, 28.5, 25.1]
S1_AVG_S = [v/1000 for v in [206, 334, 466, 1418, 2289, 3860, 6203]]
S1_FAIL  = [0.0, 0.0, 0.0, 1.6, 4.5, 17.1, 47.9]
S1_BREAK = 62.5
S1_XMAX  = 215

# ── Gráfico 01: Throughput Django ──────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Throughput — Registro de usuarios (Django + SQLite)",
         "Peticiones HTTP POST /api/user/  |  Escenario 1")

ideal = [S1_RPS[0] * u / S1_USERS[0] for u in S1_USERS]
ax.plot(S1_USERS, ideal, color=C["blue"], lw=1, ls=(0, (5, 4)),
        alpha=0.30, zorder=3, label="ideal lineal")
ax.fill_between(S1_USERS, S1_RPS, alpha=0.10, color=C["blue"], zorder=3)
ax.plot(S1_USERS, S1_RPS, color=C["blue"], lw=2.2, solid_capstyle="round",
        zorder=4, label="throughput real")
ax.scatter(S1_USERS, S1_RPS, color=C["blue"], s=42, zorder=5,
           edgecolors=C["card"], lw=1.8)

# Anotación del pico — desplazada a la izquierda del punto
ax.annotate("pico\n31.9 r/s", xy=(50, 31.9), xytext=(38, 36),
            fontsize=8, color=C["ink2"], ha="center",
            arrowprops=dict(arrowstyle="-", color=C["ink3"], lw=0.8))

zone_split(ax, S1_BREAK, S1_XMAX, 42)
ax.set_xlim(0, S1_XMAX);  ax.set_ylim(0, 42)
ax.set_xticks(S1_USERS)
ax.legend(fontsize=8.5, framealpha=0, loc="upper right",
          labelcolor=C["ink2"])
label_ax(ax, "Usuarios concurrentes", "Peticiones / segundo")
save(fig, "grafico_01_throughput.png")

# ── Gráfico 02: Latencia Django ────────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Latencia promedio por petición — Registro de usuarios",
         "Tiempo entre envío y respuesta HTTP  |  Escenario 1")

ax.fill_between(S1_USERS, S1_AVG_S, alpha=0.10, color=C["orange"], zorder=3)
ax.plot(S1_USERS, S1_AVG_S, color=C["orange"], lw=2.2, zorder=4)
ax.scatter(S1_USERS, S1_AVG_S, color=C["orange"], s=42, zorder=5,
           edgecolors=C["card"], lw=1.8)

for xu, yu, lbl in [(150, S1_AVG_S[5], "3.9 s"),
                    (200, S1_AVG_S[6], "6.2 s")]:
    ax.annotate(lbl, xy=(xu, yu), xytext=(xu - 22, yu + 0.5),
                fontsize=8.5, color=C["orange"])

zone_split(ax, S1_BREAK, S1_XMAX, 7.5)
ax.set_xlim(0, S1_XMAX);  ax.set_ylim(0, 7.5)
ax.set_xticks(S1_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}s"))
label_ax(ax, "Usuarios concurrentes", "Tiempo de respuesta (s)")
save(fig, "grafico_02_latencia.png")

# ── Gráfico 03: Tasa de fallos Django ─────────────────────────────────────
FAIL_COLORS_S1 = [C["green"], C["green"], C["green"],
                  C["yellow"], C["salmon"], C["red"], C["red"]]
FAIL_LABELS_S1 = ["Estable (0%)", "Estable (0%)", "Estable (0%)",
                  "Degradado (<2%)", "Crítico (<10%)",
                  "Colapso (≥10%)", "Colapso (≥10%)"]

fig, ax = fig_ax()
title_ax(ax, "Tasa de fallos — error 500: sqlite database is locked",
         "Escenario 1  |  colapso causado por escrituras concurrentes en SQLite")

bars = ax.bar(S1_USERS, S1_FAIL, width=12, color=FAIL_COLORS_S1,
              zorder=3, edgecolor=C["card"], lw=1.2)
for bar, val, col in zip(bars, S1_FAIL, FAIL_COLORS_S1):
    h = bar.get_height()
    lbl = f"{val:.1f}%" if val > 0 else "0%"
    if h > 12:
        ax.text(bar.get_x() + bar.get_width()/2, h/2,
                lbl, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=5)
    else:
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.8,
                lbl, ha="center", va="bottom",
                fontsize=8.5, fontweight="bold", color=col, zorder=5)

# Leyenda en esquina superior derecha (lejos de zona estable)
legend_patches = [
    mpatches.Patch(color=C["green"],  label="Estable  (0 %)"),
    mpatches.Patch(color=C["yellow"], label="Degradado  (<2 %)"),
    mpatches.Patch(color=C["salmon"], label="Crítico  (<10 %)"),
    mpatches.Patch(color=C["red"],    label="Colapso  (≥10 %)"),
]
ax.legend(handles=legend_patches, fontsize=8.5, framealpha=0,
          loc="upper right", labelcolor=C["ink2"])

ax.axvspan(S1_BREAK, S1_XMAX, color=C["zone_bad_bg"], zorder=1)
ax.axvline(S1_BREAK, color=C["zone_bad_ln"], lw=1.1,
           linestyle=(0, (5, 4)), zorder=2)
ax.set_xlim(0, S1_XMAX);  ax.set_ylim(0, 57)
ax.set_xticks(S1_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
# Etiquetas de zona al fondo del gráfico
ax.text(S1_BREAK * 0.05, 1.5, "zona estable",
        fontsize=7.5, color=C["ink3"], va="bottom")
ax.text(S1_BREAK + (S1_XMAX - S1_BREAK) * 0.05, 1.5, "zona de colapso",
        fontsize=7.5, color=C["ink3"], va="bottom")
label_ax(ax, "Usuarios concurrentes", "Tasa de fallos (%)")
save(fig, "grafico_03_fallos.png")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 2 — Emisión de credenciales SSI (ACA-Py)
# ═══════════════════════════════════════════════════════════════════════════

S2_USERS   = [1,    3,    5,    10,   15,   25  ]
S2_RPS     = [0.97, 2.89, 4.73, 9.17, 13.6, 24.0]
S2_P50_MS  = [30,   32,   37,   42,   33,   24  ]
S2_P99_MS  = [95,   66,   290,  960,  1400, 96  ]
S2_FAIL    = [0.0,  0.0,  0.0,  0.0,  42.2, 96.4]
S2_BREAK   = 18
S2_XMAX    = 28

# ── Gráfico 04: Throughput SSI ─────────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Throughput — Emisión de credenciales SSI (ACA-Py + SQLite)",
         "Escenario 2  |  >15 usuarios: ACA-Py comparte la misma instancia SQLite")

ideal = [S2_RPS[0] * u / S2_USERS[0] for u in S2_USERS]
ax.plot(S2_USERS, ideal, color=C["blue"], lw=1, ls=(0, (5, 4)),
        alpha=0.28, zorder=3, label="ideal lineal")
ax.fill_between(S2_USERS, S2_RPS, alpha=0.10, color=C["blue"], zorder=3)
ax.plot(S2_USERS, S2_RPS, color=C["blue"], lw=2.2, zorder=4,
        label="throughput real")
ax.scatter(S2_USERS, S2_RPS, color=C["blue"], s=42, zorder=5,
           edgecolors=C["card"], lw=1.8)

# Anotación: punto donde se separan las curvas
ax.annotate("req/s incluye fallos\n(rechazos rápidos)",
            xy=(25, 24.0), xytext=(18.5, 27),
            fontsize=7.5, color=C["ink3"], ha="left",
            arrowprops=dict(arrowstyle="-", color=C["ink3"], lw=0.7))

zone_split(ax, S2_BREAK, S2_XMAX, 32, label_bad="zona de degradación")
ax.set_xlim(0, S2_XMAX);  ax.set_ylim(0, 32)
ax.set_xticks(S2_USERS)
ax.legend(fontsize=8.5, framealpha=0, loc="upper left",
          labelcolor=C["ink2"], bbox_to_anchor=(0.01, 0.98))
label_ax(ax, "Usuarios concurrentes", "Peticiones / segundo")
save(fig, "grafico_04_emision_throughput.png")

# ── Gráfico 05: Latencia SSI p50/p99 ──────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Latencia de emisión — p50 vs p99",
         "Escenario 2  |  p50 ≈ constante; p99 explota por contención de SQLite")

p50_s = [v/1000 for v in S2_P50_MS]
p99_s_raw = [v/1000 for v in S2_P99_MS]
CAP = 1.6
p99_s = [min(v, CAP) for v in p99_s_raw]

ax.fill_between(S2_USERS, p99_s, alpha=0.08, color=C["orange"], zorder=2)
ax.plot(S2_USERS, p99_s, color=C["orange"], lw=2.2, zorder=4, label="p99")
ax.scatter(S2_USERS, p99_s, color=C["orange"], s=40, zorder=5,
           edgecolors=C["card"], lw=1.8)
ax.fill_between(S2_USERS, p50_s, alpha=0.12, color=C["blue"], zorder=2)
ax.plot(S2_USERS, p50_s, color=C["blue"], lw=2.2, zorder=4, label="p50")
ax.scatter(S2_USERS, p50_s, color=C["blue"], s=40, zorder=5,
           edgecolors=C["card"], lw=1.8)

# Anotar valores p99 notables (en lado derecho del punto para no solapar)
for xu, yr, vr in zip(S2_USERS, p99_s, p99_s_raw):
    if vr >= 0.25:
        lbl = f"p99: {vr:.1f}s" if vr < 1.5 else f"p99: {vr:.1f}s*"
        ax.annotate(lbl, xy=(xu, yr), xytext=(xu + 0.5, yr + 0.08),
                    fontsize=7.5, color=C["orange"], ha="left")

ax.text(S2_XMAX - 0.5, CAP - 0.08,
        "* recortado para legibilidad", fontsize=7,
        color=C["ink3"], ha="right", va="top")

zone_split(ax, S2_BREAK, S2_XMAX, CAP + 0.1, label_bad="zona de degradación")
ax.set_xlim(0, S2_XMAX);  ax.set_ylim(0, CAP + 0.1)
ax.set_xticks(S2_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1f}s"))
# Leyenda en esquina superior derecha (zona estable está a la izquierda)
ax.legend(fontsize=8.5, framealpha=0, loc="upper right",
          labelcolor=C["ink2"])
label_ax(ax, "Usuarios concurrentes", "Latencia")
save(fig, "grafico_05_emision_latencia.png")

# ── Gráfico 06: Tasa de fallos SSI ────────────────────────────────────────
FAIL_COLORS_S2 = [C["green"]] * 4 + [C["salmon"], C["red"]]

fig, ax = fig_ax()
title_ax(ax, "Tasa de fallos — Emisión de credenciales SSI",
         "Escenario 2  |  SQLite de ACA-Py se bloquea a partir de 15 usuarios")

bars = ax.bar(S2_USERS, S2_FAIL, width=1.6, color=FAIL_COLORS_S2,
              zorder=3, edgecolor=C["card"], lw=1.2)
for bar, val, col in zip(bars, S2_FAIL, FAIL_COLORS_S2):
    h = bar.get_height()
    lbl = f"{val:.1f}%" if val > 0 else "0%"
    if h > 15:
        ax.text(bar.get_x() + bar.get_width()/2, h/2,
                lbl, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=5)
    else:
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.0,
                lbl, ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=col, zorder=5)

legend_patches_s2 = [
    mpatches.Patch(color=C["green"],  label="Estable  (0 %)"),
    mpatches.Patch(color=C["salmon"], label="Degradado  (<50 %)"),
    mpatches.Patch(color=C["red"],    label="Colapso  (≥90 %)"),
]
ax.legend(handles=legend_patches_s2, fontsize=8.5, framealpha=0,
          loc="upper right", labelcolor=C["ink2"])

ax.axvspan(S2_BREAK, S2_XMAX, color=C["zone_bad_bg"], zorder=1)
ax.axvline(S2_BREAK, color=C["zone_bad_ln"], lw=1.1,
           linestyle=(0, (5, 4)), zorder=2)
ax.set_xlim(0, S2_XMAX);  ax.set_ylim(0, 112)
ax.set_xticks(S2_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.text(0.3, 2.5, "zona estable", fontsize=7.5, color=C["ink3"])
ax.text(S2_BREAK + 0.3, 2.5, "zona de colapso", fontsize=7.5, color=C["ink3"])
label_ax(ax, "Usuarios concurrentes", "Tasa de fallos (%)")
save(fig, "grafico_06_emision_fallos.png")


# ═══════════════════════════════════════════════════════════════════════════
# ESCENARIO 3 — Reservas en Besu (FlightReservation)
# ═══════════════════════════════════════════════════════════════════════════

S3_USERS   = [1,    3,    5,    10   ]
S3_TRIPS   = [6.0,  1.0,  1.0,  0.0  ]   # viajes completos equiv. 90 s
S3_FAIL    = [0.0,  87.88, 95.56, 99.99]
S3_AVG_MS  = [5000, 4610, 4967, 42   ]
S3_P50_MS  = [5000, 5000, 5000, 42   ]
S3_BREAK   = 2.0
S3_XMAX    = 12

# ── Gráfico 07: Throughput Besu ────────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Throughput — Reservas de vuelo en Besu (FlightReservation)",
         "Escenario 3  |  1 EVTOL disponible → máximo 1 viaje a la vez")

ax.fill_between(S3_USERS, S3_TRIPS, alpha=0.12, color=C["blue"], zorder=3)
ax.plot(S3_USERS, S3_TRIPS, color=C["blue"], lw=2.2, zorder=4)
ax.scatter(S3_USERS, S3_TRIPS, color=C["blue"], s=50, zorder=5,
           edgecolors=C["card"], lw=2)

for xu, yu in zip(S3_USERS, S3_TRIPS):
    offset_y = 0.35 if yu > 0 else -0.5
    va = "bottom" if yu > 0 else "top"
    ax.annotate(f"{yu:.0f}", xy=(xu, yu), xytext=(xu, yu + offset_y),
                fontsize=10, fontweight="bold", color=C["blue"],
                ha="center", va=va)

zone_split(ax, S3_BREAK, S3_XMAX, 8,
           label_ok="zona estable",
           label_bad="zona de congestión")
ax.set_xlim(0, S3_XMAX);  ax.set_ylim(0, 8)
ax.set_xticks(S3_USERS)

# Nota explicativa
ax.text(0.5, 0.02,
        "Con N usuarios compartiendo 1 cuenta Besu y 1 EVTOL, los N−1 nonces "
        "fallidos bloquean el nonce útil → throughput baja al aumentar usuarios.",
        transform=ax.transAxes, fontsize=7.5, color=C["ink3"],
        ha="left", va="bottom", wrap=True)

label_ax(ax, "Usuarios concurrentes", "Viajes completos (equiv. 90 s)")
save(fig, "grafico_07_besu_throughput.png")

# ── Gráfico 08: Tasa de fallos Besu ───────────────────────────────────────
FAIL_COLORS_S3 = [C["green"], C["red"], C["red"], C["red"]]

fig, ax = fig_ax()
title_ax(ax, "Tasa de fallos — Reservas en Besu",
         "Escenario 3  |  colapso desde 3 usuarios por state machine del EVTOL")

bars = ax.bar(S3_USERS, S3_FAIL, width=1.3, color=FAIL_COLORS_S3,
              zorder=3, edgecolor=C["card"], lw=1.2)
for bar, val, col in zip(bars, S3_FAIL, FAIL_COLORS_S3):
    h = bar.get_height()
    lbl = f"{val:.1f}%"
    if h > 15:
        ax.text(bar.get_x() + bar.get_width()/2, h/2,
                lbl, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="white", zorder=5)
    else:
        ax.text(bar.get_x() + bar.get_width()/2, h + 1.0,
                lbl, ha="center", va="bottom",
                fontsize=9.5, fontweight="bold", color=col, zorder=5)

legend_patches_s3 = [
    mpatches.Patch(color=C["green"], label="Estable  (0 %)"),
    mpatches.Patch(color=C["red"],   label="Colapso  (≥88 %)"),
]
ax.legend(handles=legend_patches_s3, fontsize=8.5, framealpha=0,
          loc="upper right", labelcolor=C["ink2"])

ax.axvspan(S3_BREAK, S3_XMAX, color=C["zone_bad_bg"], zorder=1)
ax.axvline(S3_BREAK, color=C["zone_bad_ln"], lw=1.1,
           linestyle=(0, (5, 4)), zorder=2)
ax.set_xlim(0, S3_XMAX);  ax.set_ylim(0, 112)
ax.set_xticks(S3_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.text(0.12, 2.0, "estable", fontsize=7.5, color=C["ink3"])
ax.text(S3_BREAK + 0.15, 2.0, "colapso", fontsize=7.5, color=C["ink3"])
label_ax(ax, "Usuarios concurrentes", "Tasa de fallos (%)")
save(fig, "grafico_08_besu_fallos.png")

# ── Gráfico 09: Latencia Besu ──────────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Latencia — Reservas en Besu (createReservation)",
         "Escenario 3  |  1–5u: espera on-chain ~5 s/bloque QBFT  ·  10u: rechazo RPC ~42 ms")

avg_s = [v/1000 for v in S3_AVG_MS]
p50_s = [v/1000 for v in S3_P50_MS]

ax.fill_between(S3_USERS, avg_s, alpha=0.09, color=C["orange"], zorder=2)
ax.plot(S3_USERS, avg_s, color=C["orange"], lw=2.2, zorder=4, label="Promedio")
ax.scatter(S3_USERS, avg_s, color=C["orange"], s=44, zorder=5,
           edgecolors=C["card"], lw=1.8)
ax.fill_between(S3_USERS, p50_s, alpha=0.12, color=C["blue"], zorder=2)
ax.plot(S3_USERS, p50_s, color=C["blue"], lw=2.2, zorder=4, label="p50")
ax.scatter(S3_USERS, p50_s, color=C["blue"], s=44, zorder=5,
           edgecolors=C["card"], lw=1.8)

# Anotación 10u — a la derecha y arriba para no tapar la caída
ax.annotate("10u: rechazo RPC\n\"nonce too distant\"\n~42 ms",
            xy=(10, 0.042), xytext=(8.2, 2.0),
            fontsize=7.5, color=C["ink3"], ha="left",
            arrowprops=dict(arrowstyle="->", color=C["ink3"], lw=0.8))

ax.legend(fontsize=8.5, framealpha=0, loc="upper right",
          labelcolor=C["ink2"])
zone_split(ax, S3_BREAK, S3_XMAX, 6.2,
           label_ok="on-chain (lento)", label_bad="rechazo RPC (rápido)")
ax.set_xlim(0, S3_XMAX);  ax.set_ylim(0, 6.2)
ax.set_xticks(S3_USERS)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}s"))
label_ax(ax, "Usuarios concurrentes", "Latencia (createReservation)")
save(fig, "grafico_09_besu_latencia.png")

print("\nTodos los gráficos generados correctamente.")
