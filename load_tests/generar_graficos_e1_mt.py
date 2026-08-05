"""
Genera los 3 gráficos del Escenario 1 con datos multitenant + PostgreSQL.
Lee directamente los CSV de Locust (e1_mt_u{N}_stats.csv) y produce:
  grafico_01_throughput.png  — Throughput (req/s) vs usuarios
  grafico_02_latencia.png    — Latencia p50 / p95 / p99 vs usuarios
  grafico_03_fallos.png      — Tasa de fallos (%) vs usuarios

Uso:
  cd SSI_App
  source venv/bin/activate
  python load_tests/generar_graficos_e1_mt.py
"""

import csv
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

RESULTS = os.path.join(os.path.dirname(__file__), "resultados")
OUT = RESULTS

USER_COUNTS = [10, 25, 50, 100, 200, 300, 500]

# ── Paleta (igual que generar_todos_graficos.py) ─────────────────────────────
C = {
    "card":   "#ffffff",
    "ink":    "#0f1217",
    "ink2":   "#52555f",
    "ink3":   "#9399a6",
    "grid":   "#e4e8f0",
    "blue":   "#2563eb",
    "orange": "#d97706",
    "green":  "#16a34a",
    "purple": "#7c3aed",
    "red":    "#dc2626",
    "yellow": "#ca8a04",
    "salmon": "#e07050",
    "zone_bad_bg": (0.86, 0.20, 0.20, 0.055),
    "zone_bad_ln": (0.86, 0.20, 0.20, 0.35),
}

FIG_W, FIG_H = 9.0, 4.5


def read_stats(n):
    path = os.path.join(RESULTS, f"e1_mt_u{n}_stats.csv")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Name"] == "POST /api/user/":
                req   = int(row["Request Count"])
                fail  = int(row["Failure Count"])
                rps   = float(row["Requests/s"])
                p50   = float(row["50%"])
                p95   = float(row["95%"])
                p99   = float(row["99%"])
                fail_pct = (fail / req * 100) if req > 0 else 0.0
                return {"rps": rps, "fail": fail_pct,
                        "p50": p50, "p95": p95, "p99": p99,
                        "req": req, "fail_abs": fail}
    raise ValueError(f"No se encontró la fila POST /api/user/ en e1_mt_u{n}_stats.csv")


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


def save(fig, fname):
    plt.tight_layout(pad=1.4)
    fig.savefig(os.path.join(OUT, fname), dpi=155, bbox_inches="tight",
                facecolor=C["card"])
    plt.close(fig)
    print(f"  {fname}")


# ── Leer datos ────────────────────────────────────────────────────────────────
data = {}
for n in USER_COUNTS:
    try:
        data[n] = read_stats(n)
        print(f"u={n:3d}  rps={data[n]['rps']:.1f}  "
              f"fail={data[n]['fail']:.1f}%  "
              f"p50={data[n]['p50']:.0f}ms  "
              f"p95={data[n]['p95']:.0f}ms  "
              f"p99={data[n]['p99']:.0f}ms")
    except Exception as e:
        print(f"ERROR u={n}: {e}")
        data[n] = None

valid = [n for n in USER_COUNTS if data[n] is not None]
users   = valid
rps     = [data[n]["rps"]  for n in valid]
fail    = [data[n]["fail"] for n in valid]
p50_ms  = [data[n]["p50"]  for n in valid]
p95_ms  = [data[n]["p95"]  for n in valid]
p99_ms  = [data[n]["p99"]  for n in valid]

# Convertir a segundos para los gráficos de latencia
p50_s = [v / 1000 for v in p50_ms]
p95_s = [v / 1000 for v in p95_ms]
p99_s = [v / 1000 for v in p99_ms]

XMAX  = max(users) * 1.08
YMAX_LAT = max(max(p99_s) * 1.15, 1.0)

# Determinar punto de ruptura (primera vez que fail > 5%)
break_x = None
for i, n in enumerate(users):
    if fail[i] > 5.0:
        break_x = (users[i - 1] + n) / 2 if i > 0 else n * 0.8
        break


# ── Gráfico 01: Throughput ────────────────────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Throughput — Registro de usuarios (Django + PostgreSQL + ACA-Py multitenant)",
         "POST /api/user/  |  Escenario 1 — arquitectura multitenant")

ideal = [rps[0] * n / users[0] for n in users]
ax.plot(users, ideal, color=C["blue"], lw=1, ls=(0, (5, 4)),
        alpha=0.30, zorder=3, label="ideal lineal")
ax.fill_between(users, rps, alpha=0.10, color=C["blue"], zorder=3)
ax.plot(users, rps, color=C["blue"], lw=2.2, solid_capstyle="round",
        zorder=4, label="throughput real")
ax.scatter(users, rps, color=C["blue"], s=42, zorder=5,
           edgecolors=C["card"], lw=1.8)

# Anotar pico
peak_idx = rps.index(max(rps))
ax.annotate(f"pico\n{max(rps):.1f} r/s",
            xy=(users[peak_idx], rps[peak_idx]),
            xytext=(users[peak_idx] - XMAX * 0.12, rps[peak_idx] + max(rps) * 0.10),
            fontsize=8, color=C["ink2"], ha="center",
            arrowprops=dict(arrowstyle="-", color=C["ink3"], lw=0.8))

if break_x:
    ax.axvspan(break_x, XMAX, color=C["zone_bad_bg"], zorder=1)
    ax.axvline(break_x, color=C["zone_bad_ln"], lw=1.1, ls=(0, (5, 4)), zorder=2)
    ax.text(break_x * 0.05, max(rps) * 0.04, "zona estable",
            fontsize=7.5, color=C["ink3"])
    ax.text(break_x + (XMAX - break_x) * 0.05, max(rps) * 0.04, "zona de colapso",
            fontsize=7.5, color=C["ink3"])

ax.set_xlim(0, XMAX)
ax.set_ylim(0, max(rps) * 1.25)
ax.set_xticks(users)
ax.legend(fontsize=8.5, framealpha=0, loc="upper right", labelcolor=C["ink2"])
label_ax(ax, "Usuarios concurrentes", "Peticiones / segundo")
save(fig, "grafico_01_throughput.png")


# ── Gráfico 02: Latencia p50 / p95 / p99 ─────────────────────────────────────
fig, ax = fig_ax()
title_ax(ax, "Latencia de respuesta — p50 / p95 / p99",
         "POST /api/user/  |  Escenario 1 — ACA-Py multitenant + PostgreSQL")

# p99 al fondo con relleno
ax.fill_between(users, p99_s, alpha=0.07, color=C["red"], zorder=2)
ax.plot(users, p99_s, color=C["red"], lw=2.0, zorder=4, label="p99", ls="--")
ax.scatter(users, p99_s, color=C["red"], s=38, zorder=5,
           edgecolors=C["card"], lw=1.5)

# p95
ax.fill_between(users, p95_s, alpha=0.08, color=C["orange"], zorder=2)
ax.plot(users, p95_s, color=C["orange"], lw=2.0, zorder=4, label="p95")
ax.scatter(users, p95_s, color=C["orange"], s=38, zorder=5,
           edgecolors=C["card"], lw=1.5)

# p50 encima
ax.fill_between(users, p50_s, alpha=0.12, color=C["blue"], zorder=3)
ax.plot(users, p50_s, color=C["blue"], lw=2.2, zorder=5, label="p50")
ax.scatter(users, p50_s, color=C["blue"], s=42, zorder=6,
           edgecolors=C["card"], lw=1.8)

if break_x:
    ax.axvspan(break_x, XMAX, color=C["zone_bad_bg"], zorder=1)
    ax.axvline(break_x, color=C["zone_bad_ln"], lw=1.1, ls=(0, (5, 4)), zorder=2)
    ax.text(break_x * 0.05, YMAX_LAT * 0.03, "zona estable",
            fontsize=7.5, color=C["ink3"])
    ax.text(break_x + (XMAX - break_x) * 0.05, YMAX_LAT * 0.03, "zona de colapso",
            fontsize=7.5, color=C["ink3"])

ax.set_xlim(0, XMAX)
ax.set_ylim(0, YMAX_LAT)
ax.set_xticks(users)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1f}s"))
ax.legend(fontsize=8.5, framealpha=0, loc="upper left", labelcolor=C["ink2"])
label_ax(ax, "Usuarios concurrentes", "Tiempo de respuesta")
save(fig, "grafico_02_latencia.png")


# ── Gráfico 03: Tasa de fallos ────────────────────────────────────────────────
def fail_color(f):
    if f < 1:   return C["green"]
    if f < 10:  return C["yellow"]
    if f < 50:  return C["salmon"]
    return C["red"]

bar_colors = [fail_color(f) for f in fail]

fig, ax = fig_ax()
title_ax(ax, "Tasa de fallos — Registro de usuarios (multitenant)",
         "Escenario 1  |  HTTP 500 bajo carga sostenida")

bars = ax.bar(users, fail, width=[u * 0.10 for u in users],
              color=bar_colors, zorder=3, edgecolor=C["card"], lw=1.2)

for bar, val, col in zip(bars, fail, bar_colors):
    h = bar.get_height()
    lbl = f"{val:.1f}%"
    if h > 12:
        ax.text(bar.get_x() + bar.get_width() / 2, h / 2,
                lbl, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=5)
    else:
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1.0,
                lbl, ha="center", va="bottom",
                fontsize=8.5, fontweight="bold", color=col, zorder=5)

legend_patches = [
    mpatches.Patch(color=C["green"],  label="Estable  (< 1 %)"),
    mpatches.Patch(color=C["yellow"], label="Degradado  (1–10 %)"),
    mpatches.Patch(color=C["salmon"], label="Crítico  (10–50 %)"),
    mpatches.Patch(color=C["red"],    label="Colapso  (≥ 50 %)"),
]
ax.legend(handles=legend_patches, fontsize=8.5, framealpha=0,
          loc="upper right", labelcolor=C["ink2"])

if break_x:
    ax.axvspan(break_x, XMAX, color=C["zone_bad_bg"], zorder=1)
    ax.axvline(break_x, color=C["zone_bad_ln"], lw=1.1, ls=(0, (5, 4)), zorder=2)
    ax.text(break_x * 0.05, max(fail) * 0.02, "zona estable",
            fontsize=7.5, color=C["ink3"])
    ax.text(break_x + (XMAX - break_x) * 0.05, max(fail) * 0.02, "zona de colapso",
            fontsize=7.5, color=C["ink3"])

ax.set_xlim(0, XMAX)
ax.set_ylim(0, max(fail) * 1.20 + 5)
ax.set_xticks(users)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
label_ax(ax, "Usuarios concurrentes", "Tasa de fallos (%)")
save(fig, "grafico_03_fallos.png")

print("\nGráficos E1 multitenant generados correctamente.")
