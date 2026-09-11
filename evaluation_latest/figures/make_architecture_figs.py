"""
Generates the architecture / pipeline figures for the manuscript.

Fig A: end-to-end ten-stage pipeline (data -> context -> plan -> specialists
       -> reasoning -> executive -> recommendation -> explanation), with the
       TRUSTAI governance layer shown as a cross-cutting band.
Fig B: TRUSTAI governance loop (pre-execution gate + posterior update).
Fig C: benchmark construction / perturbation methodology.

All are vector-quality PNG at 300 DPI for Elsevier.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

OUT = os.path.dirname(os.path.abspath(__file__))

GREEN = "#2f6f4e"
LGREEN = "#e3efe8"
BLUE = "#1f4e79"
LBLUE = "#e4edf6"
ORANGE = "#a5561b"
LORANGE = "#fbeee2"
GREY = "#555555"
LGREY = "#f0f0f0"
RED = "#8c2f2f"
LRED = "#f8e8e8"


def box(ax, x, y, w, h, text, fc, ec, fs=8.5, weight="bold", tc="#111111"):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0.012,rounding_size=0.02",
                       linewidth=1.1, facecolor=fc, edgecolor=ec)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight=weight, color=tc, linespacing=1.35)


def arrow(ax, x1, y1, x2, y2, color=GREY, lw=1.3, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=11, linewidth=lw,
                                 color=color, shrinkA=0, shrinkB=0))


# ======================================================================
# Figure A -- full pipeline
# ======================================================================
def figure_architecture():
    fig, ax = plt.subplots(figsize=(11.2, 7.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, 7.4); ax.axis("off")

    # --- input ---
    box(ax, 2.5, 6.85, 3.4, 0.42,
        "Farmer query  +  crop  +  (latitude, longitude)", LBLUE, BLUE, 9)
    arrow(ax, 4.2, 6.85, 4.2, 6.55)

    # --- stage 1: crop knowledge ---
    box(ax, 2.25, 6.08, 3.9, 0.45,
        "Stage 1  Crop Knowledge\nprofile lookup / LLM synthesis + cache", LGREEN, GREEN, 8)
    arrow(ax, 4.2, 6.08, 4.2, 5.78)

    # --- stage 2: five collectors ---
    ax.text(0.15, 5.55, "Stage 2   Parallel data acquisition", fontsize=8.5,
            fontweight="bold", color=GREY)
    srcs = [("Weather\nOpen-Meteo\n(live API)", LBLUE, BLUE),
            ("Soil\nSoilGrids\n(live API)", LBLUE, BLUE),
            ("Satellite\nSentinel-2\n(live GEE)", LBLUE, BLUE),
            ("Market\nAgmarknet\n(live API)", LBLUE, BLUE),
            ("Historical\nSQLite\n(local)", LGREY, GREY)]
    for i, (t, fc, ec) in enumerate(srcs):
        box(ax, 0.10 + i * 1.60, 4.72, 1.46, 0.72, t, fc, ec, 7.0, "normal")
        arrow(ax, 0.10 + i * 1.60 + 0.73, 4.72, 4.2, 4.42, color="#999999", lw=0.9)

    # --- stage 3: context ---
    box(ax, 1.75, 3.97, 4.9, 0.44,
        "Stage 3  Context Fusion  (deterministic; no LLM)", LGREY, GREY, 8)
    arrow(ax, 4.2, 3.97, 4.2, 3.67)

    # --- stage 4: planner ---
    box(ax, 1.75, 3.22, 4.9, 0.44,
        "Stage 4  Dynamic Planner  (LLM + deterministic fallback)\n"
        r"selects $A_{\mathrm{sel}} \subseteq A$ by intent and data availability",
        LGREEN, GREEN, 7.6)
    arrow(ax, 4.2, 3.22, 4.2, 2.92)

    # --- stage 5: specialists ---
    ax.text(0.15, 2.72, "Stage 5   Specialist agents (concurrent)", fontsize=8.5,
            fontweight="bold", color=GREY)
    ags = ["Weather\nAgent", "Soil\nAgent", "Satellite\nAgent",
           "Market\nAgent", "Historical\nAgent"]
    for i, t in enumerate(ags):
        box(ax, 0.10 + i * 1.60, 1.95, 1.46, 0.6, t, LORANGE, ORANGE, 7.2)
        arrow(ax, 0.10 + i * 1.60 + 0.73, 1.95, 4.2, 1.68, color="#999999", lw=0.9)

    # --- stage 6-9 chain ---
    box(ax, 1.55, 1.22, 5.3, 0.42,
        "Stage 6  Collaborative Reasoning   evidence graph "
        r"$\rightarrow$ conflicts $\rightarrow$ consensus $\rightarrow$ fusion",
        LGREEN, GREEN, 7.6)
    arrow(ax, 4.2, 1.22, 4.2, 0.98)
    box(ax, 1.55, 0.56, 5.3, 0.40,
        "Stage 7  Executive Decision (rule engine)   "
        r"$\rightarrow$   Stage 8  Recommendation (LLM)", LGREY, GREY, 7.6)
    arrow(ax, 4.2, 0.56, 4.2, 0.34)
    box(ax, 2.05, 0.0, 4.3, 0.32,
        "Stage 9  Explainability   trace, ranked evidence, limitations",
        LBLUE, BLUE, 7.6)

    # --- TRUSTAI band (cross-cutting) ---
    ax.add_patch(Rectangle((8.28, 0.0), 1.68, 5.44, facecolor=LRED,
                           edgecolor=RED, linewidth=1.1, zorder=0))
    ax.text(9.12, 2.72,
            "Stage 10\nTRUSTAI\ngovernance\n\n"
            r"pre-exec gate $\rightarrow$" "\nauto / review /\nreject\n\n"
            "post-exec\nBeta-Bernoulli\nposterior update\n\n"
            "(cross-cutting:\nwraps every\nspecialist call)",
            ha="center", va="center", fontsize=7.1, color="#4a1f1f",
            fontweight="bold", linespacing=1.5)
    arrow(ax, 8.28, 2.25, 6.95, 2.25, color=RED, lw=1.0, style="<|-|>")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_architecture.png"), dpi=600,
                bbox_inches="tight")
    plt.close(fig)


# ======================================================================
# Figure B -- TRUSTAI governance loop
# ======================================================================
def figure_trustai():
    fig, ax = plt.subplots(figsize=(9.6, 3.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.5); ax.axis("off")

    box(ax, 0.05, 1.45, 1.5, 0.62,
        r"agent $a_i$" "\nrequested", LGREY, GREY, 8)
    arrow(ax, 1.55, 1.76, 2.05, 1.76)

    box(ax, 2.05, 1.35, 1.95, 0.82,
        "pre-execution\nreview\n" r"$\mathbb{E}[U(\cdot)]$ over" "\n"
        "{exec, review, reject}", LRED, RED, 7.4, "normal")
    arrow(ax, 4.0, 1.76, 4.55, 1.76)

    box(ax, 4.55, 1.45, 1.6, 0.62, "execute\nspecialist", LORANGE, ORANGE, 8)
    arrow(ax, 6.15, 1.76, 6.7, 1.76)

    box(ax, 6.7, 1.35, 1.95, 0.82,
        "outcome evidence\n" r"success: $\alpha_i \leftarrow \alpha_i + w$" "\n"
        r"failure: $\beta_i \leftarrow \beta_i + w$", LRED, RED, 7.4, "normal")

    # feedback loop
    arrow(ax, 7.67, 1.35, 7.67, 0.72, color=RED)
    arrow(ax, 7.67, 0.72, 3.02, 0.72, color=RED)
    arrow(ax, 3.02, 0.72, 3.02, 1.35, color=RED)
    ax.text(5.35, 0.52, r"posterior $\mathrm{Beta}(\alpha_i,\beta_i)$ carried to the next request",
            ha="center", fontsize=7.8, color=RED, style="italic")

    # reject path
    arrow(ax, 3.02, 2.17, 3.02, 2.72, color=RED)
    ax.text(3.02, 2.88, "reject  →  agent skipped, marked rejected",
            ha="center", fontsize=7.6, color=RED)

    ax.text(0.05, 0.15,
            r"$\mu_i=\dfrac{\alpha_i}{\alpha_i+\beta_i}$,   "
            r"$\sigma_i^2=\dfrac{\alpha_i\beta_i}{(\alpha_i+\beta_i)^2(\alpha_i+\beta_i+1)}$,   "
            r"prior $\mathrm{Beta}(2,2)$",
            fontsize=8.4, color="#333333")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_trustai_loop.png"), dpi=600,
                bbox_inches="tight")
    plt.close(fig)


# ======================================================================
# Figure C -- benchmark construction
# ======================================================================
def figure_benchmark():
    fig, ax = plt.subplots(figsize=(9.8, 3.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.2); ax.axis("off")

    steps = [
        ("1. clone a REAL\ncollected context\n(genuine API responses)", LBLUE, BLUE),
        ("2. neutralise\nall fields to\nmid-optimal baseline", LGREY, GREY),
        ("3. apply exactly ONE\nperturbation crossing a\ncrop-profile threshold", LORANGE, ORANGE),
        ("4. derive ground truth\nfrom the crossed\nthreshold", LGREEN, GREEN),
        ("5. replay via\nCollectorPatch\n(fully reproducible)", LGREEN, GREEN),
    ]
    for i, (t, fc, ec) in enumerate(steps):
        box(ax, 0.05 + i * 2.0, 1.35, 1.82, 1.0, t, fc, ec, 7.2, "normal")
        if i < len(steps) - 1:
            arrow(ax, 0.05 + i * 2.0 + 1.82, 1.85, 0.05 + (i + 1) * 2.0, 1.85)

    ax.text(5.0, 0.92,
            "single-variable isolation: every scenario differs from the neutral baseline in exactly one field",
            ha="center", fontsize=8.2, style="italic", color="#333333")
    ax.text(5.0, 0.45,
            r"ground truth $d^{\ast}$ constrained to the system's own closed decision vocabulary "
            r"$\mathcal{D}$, $|\mathcal{D}|=6$",
            ha="center", fontsize=8.2, color="#333333")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_benchmark_construction.png"), dpi=600,
                bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    figure_architecture()
    figure_trustai()
    figure_benchmark()
    print("wrote fig_architecture.png, fig_trustai_loop.png, fig_benchmark_construction.png")
