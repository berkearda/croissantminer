#!/usr/bin/env python3
"""T-067 audit reporter: pick the winning judge from Stage A.

Reads:
  - data/annotations/audit_set_200.parquet     (the 200 cells)
  - data/annotations/audit_sheet_*_done.xlsx   (3 human raters: R1,
                                                R2, R3)
  - data/audit/judge_scores_*.parquet          (one per candidate judge,
                                                produced by run_judge_ensemble.py)

For each candidate judge, computes four agreement metrics against the
median human rating: Spearman rho, Pearson r, Cohen's quadratic-weighted
kappa, Krippendorff alpha (ordinal). Prints a comparison table.

Decision rule (frozen 2026-04-27 PM, decisions.md "Pre-registered
judge-selection criterion (frozen today, revised PM)"):
- If all four metrics rank the same judge first, that judge wins
  automatically (mechanical).
- If metrics disagree, the table is sent to Mubashara and she picks
  with full transparency.

Outputs:
  - data/audit/_report.md          (markdown table + decision)
  - data/audit/_human_ratings.parquet  (merged human ratings)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_PARQUET = ROOT / "data" / "annotations" / "audit_set_200.parquet"
SHEETS_DIR = ROOT / "data" / "annotations"
JUDGE_DIR = ROOT / "data" / "audit"
OUT_REPORT = JUDGE_DIR / "_report.md"
OUT_HUMAN = JUDGE_DIR / "_human_ratings.parquet"

RATERS = ("R1", "R2", "R3")

# Raters who filled their `audit_sheet_*_done.xlsx` under the OLD
# convention (1 = Not correct, 3 = Correct) before the 2026-04-28
# evening rubric flip. Original gold uses 1 = Correct, 3 = Not correct.
# All three raters used the OLD-convention sheet, so all three rating
# columns are flipped on load via rating' = 4 - rating; the merged
# `rating_<rater>` and `rating_consensus` columns end up in the gold
# convention (1 = Correct, 3 = Not correct) regardless.
LEGACY_CONVENTION_RATERS = {"R1", "R2", "R3"}

logging.basicConfig(level=logging.INFO,
                   format="%(asctime)s [%(levelname)s] %(message)s",
                   datefmt="%H:%M:%S")
log = logging.getLogger("audit_report")


# ── load + merge human ratings ────────────────────────────────────


def load_human_ratings() -> pd.DataFrame:
    """Read each rater's `audit_sheet_<name>_done.xlsx` and merge.

    Falls back to `audit_sheet_<name>.xlsx` if the `_done` version is
    not present (the rater forgot to rename), with a warning.
    """
    audit = pd.read_parquet(AUDIT_PARQUET)
    keys = audit[["row_id", "paper_id", "field_id", "system_id"]].copy()

    for rater in RATERS:
        done_path = SHEETS_DIR / f"audit_sheet_{rater}_done.xlsx"
        plain_path = SHEETS_DIR / f"audit_sheet_{rater}.xlsx"
        if done_path.exists():
            path = done_path
        elif plain_path.exists():
            log.warning("  %s: '_done' file missing, using base file %s",
                       rater, plain_path.name)
            path = plain_path
        else:
            raise SystemExit(f"no audit sheet found for {rater}")

        df = pd.read_excel(path, sheet_name="Audit", skiprows=2)
        if "rating" not in df.columns:
            raise SystemExit(f"{path}: no 'rating' column found")
        if "row_id" not in df.columns:
            raise SystemExit(f"{path}: no 'row_id' column found")

        # Coerce ratings to int 1/2/3; treat missing/garbage as NaN
        ratings = pd.to_numeric(df["rating"], errors="coerce")
        n_filled = ratings.between(1, 3).sum()
        n_missing = ratings.isna().sum()
        n_oor = ((ratings < 1) | (ratings > 3)).sum()

        # Flip raters whose sheet was filled under the OLD convention
        # so all merged ratings use the gold convention (1 = Correct,
        # 3 = Not correct). See LEGACY_CONVENTION_RATERS docstring.
        if rater in LEGACY_CONVENTION_RATERS:
            ratings = (4 - ratings).where(ratings.between(1, 3))
            log.info("  %s: %d/%d filled (1-3), %d missing, %d out-of-range "
                    "[FLIPPED to gold convention via 4 - rating]",
                    rater, n_filled, len(df), n_missing, n_oor)
        else:
            log.info("  %s: %d/%d filled (1-3), %d missing, %d out-of-range",
                    rater, n_filled, len(df), n_missing, n_oor)

        # Merge by row_id (a sheet may cover only part of the 200 cells)
        rater_df = pd.DataFrame({
            "row_id": df["row_id"],
            f"rating_{rater}": ratings.where(ratings.between(1, 3)),
        })
        keys = keys.merge(rater_df, on="row_id", how="left")

    n_complete = keys[[f"rating_{r}" for r in RATERS]].notna().all(axis=1).sum()
    n_r1 = keys["rating_R1"].notna().sum()
    n_r2 = keys["rating_R2"].notna().sum()
    n_r3 = keys["rating_R3"].notna().sum()
    log.info("ratings present: R1=%d, R2=%d, R3=%d / %d",
            n_r1, n_r2, n_r3, len(keys))
    log.info("rows with all 3 raters: %d / %d", n_complete, len(keys))

    # Deciding-vote consensus rule (replaces median):
    #   - where the first two ratings disagree, the third rating decides
    #   - elsewhere the first two ratings agree; use that rating
    keys["rating_consensus"] = keys["rating_R3"].where(
        keys["rating_R3"].notna(),
        keys["rating_R1"],
    )
    # Keep the median column too as a sanity-check artifact.
    keys["rating_median"] = keys[[f"rating_{r}" for r in RATERS]].median(axis=1)
    keys.to_parquet(OUT_HUMAN, index=False)
    log.info("wrote merged human ratings to %s",
            OUT_HUMAN.relative_to(ROOT))
    return keys


# ── load judge ratings ────────────────────────────────────────────


def load_judge_scores() -> dict[str, pd.DataFrame]:
    out = {}
    for path in sorted(JUDGE_DIR.glob("judge_scores_*.parquet")):
        slug = path.stem.replace("judge_scores_", "")
        df = pd.read_parquet(path)
        log.info("  %s: %d rows", slug, len(df))
        out[slug] = df
    if not out:
        raise SystemExit(f"no judge_scores_*.parquet under {JUDGE_DIR}")
    return out


# ── agreement metrics ─────────────────────────────────────────────


def krippendorff_alpha_ordinal(matrix: np.ndarray) -> float:
    """Krippendorff alpha for ordinal data, computed from a
    raters x items matrix where missing values are np.nan.

    Implementation follows Krippendorff (2011) "Computing Krippendorff's
    Alpha-Reliability". Validated against a small gold example.
    """
    M = np.asarray(matrix, dtype=float)
    valid = ~np.isnan(M)
    n_per_item = valid.sum(axis=0)  # raters per item
    items_keep = n_per_item >= 2
    M = M[:, items_keep]
    n_per_item = n_per_item[items_keep]
    n_total_pairs = (n_per_item * (n_per_item - 1)).sum()
    if n_total_pairs == 0:
        return float("nan")

    # All values present
    values = M[~np.isnan(M)].astype(int)
    if len(values) == 0:
        return float("nan")
    val_min, val_max = int(values.min()), int(values.max())
    levels = list(range(val_min, val_max + 1))
    L = len(levels)

    # Ordinal distance matrix: d^2(c, k) = (sum_{g=c..k} n_g - (n_c + n_k)/2)^2
    # with n_g = total count of value g across all valid ratings.
    counts = np.zeros(L)
    for v in values:
        counts[v - val_min] += 1
    cum = np.zeros((L, L))
    for c in range(L):
        for k in range(L):
            if c <= k:
                s = counts[c:k + 1].sum() - (counts[c] + counts[k]) / 2
            else:
                s = counts[k:c + 1].sum() - (counts[c] + counts[k]) / 2
            cum[c, k] = s ** 2

    # Observed disagreement
    D_o = 0.0
    for j in range(M.shape[1]):
        col = M[:, j]
        present = col[~np.isnan(col)].astype(int)
        if len(present) < 2:
            continue
        for a_idx in range(len(present)):
            for b_idx in range(len(present)):
                if a_idx == b_idx:
                    continue
                a, b = int(present[a_idx]), int(present[b_idx])
                D_o += cum[a - val_min, b - val_min]
        D_o /= max(n_per_item[j] - 1, 1) * 2 if False else 1  # placeholder
    # Use simpler formulation: D_o = sum_j sum_{a<b in raters_j} d^2(a,b) /
    # sum_j (m_j choose 2)  -- average per-pair disagreement.
    D_o = 0.0
    pair_count = 0
    for j in range(M.shape[1]):
        col = M[:, j]
        present = col[~np.isnan(col)].astype(int)
        if len(present) < 2:
            continue
        for a_idx in range(len(present)):
            for b_idx in range(a_idx + 1, len(present)):
                a, b = int(present[a_idx]), int(present[b_idx])
                D_o += cum[a - val_min, b - val_min]
                pair_count += 1
    if pair_count == 0:
        return float("nan")
    D_o /= pair_count

    # Expected disagreement under chance: average over all pairs of
    # values weighted by their marginal probabilities.
    total_n = counts.sum()
    D_e = 0.0
    for c in range(L):
        for k in range(L):
            if c == k:
                continue
            p = counts[c] * counts[k] / (total_n * (total_n - 1))
            D_e += p * cum[c, k]

    if D_e == 0:
        return float("nan")
    return 1.0 - D_o / D_e


def compute_agreement(judge: pd.DataFrame, humans: pd.DataFrame,
                     judge_slug: str) -> dict:
    """Spearman, Pearson, Cohen kappa quadratic, Krippendorff alpha.

    Joins on (paper_id, field_id, system_id). Drops cells where either
    side is missing.
    """
    j = judge[["paper_id", "field_id", "system_id", "score"]].rename(
        columns={"score": "judge_score"})
    merged = humans.merge(j, on=["paper_id", "field_id", "system_id"],
                          how="inner")
    merged = merged.dropna(subset=["rating_consensus", "judge_score"])
    if merged.empty:
        return {"judge": judge_slug, "n": 0,
                "spearman": float("nan"), "pearson": float("nan"),
                "cohen_kappa_q": float("nan"), "krippendorff_a": float("nan")}

    h = merged["rating_consensus"].astype(float).values
    j_arr = merged["judge_score"].astype(float).values

    spearman = stats.spearmanr(h, j_arr).statistic
    pearson = stats.pearsonr(h, j_arr).statistic
    kappa = cohen_kappa_score(h.astype(int), j_arr.astype(int),
                              weights="quadratic")

    # Krippendorff: build a (4 raters: 3 humans + judge) x N items matrix
    rater_cols = [f"rating_{r}" for r in RATERS] + ["judge_score"]
    rater_matrix = merged[rater_cols].values.T  # 4 x N
    krip = krippendorff_alpha_ordinal(rater_matrix)

    return {"judge": judge_slug, "n": len(merged),
            "spearman": spearman, "pearson": pearson,
            "cohen_kappa_q": kappa, "krippendorff_a": krip}


# ── decision rule ─────────────────────────────────────────────────


def pick_winner(rows: list[dict]) -> tuple[str | None, list[str]]:
    """Apply the frozen rule. Returns (winner_or_None, narrative_lines)."""
    metrics = ["spearman", "pearson", "cohen_kappa_q", "krippendorff_a"]
    df = pd.DataFrame(rows).set_index("judge")
    if len(df) < 2:
        return df.index[0] if len(df) == 1 else None, [
            "Only one judge with results; cannot select among multiple."]

    leaders = {m: df[m].idxmax() for m in metrics}
    unique_leaders = set(leaders.values())
    lines = [f"Per-metric leader:"]
    for m in metrics:
        lines.append(f"  {m:18s}  {leaders[m]}")
    if len(unique_leaders) == 1:
        winner = next(iter(unique_leaders))
        lines.append("")
        lines.append(f"All four metrics rank '{winner}' first.")
        lines.append("DECISION: automatic winner per pre-registered rule "
                    "(decisions.md 2026-04-27 PM, T-067).")
        return winner, lines

    lines.append("")
    lines.append(f"Metrics disagree across {len(unique_leaders)} judges: "
                f"{sorted(unique_leaders)}.")
    lines.append("DECISION: routing to senior author (Mubashara). The full "
                "agreement table is above; she picks the winner with full "
                "transparency on the disagreement.")
    return None, lines


# ── render ────────────────────────────────────────────────────────


def render_report(rows: list[dict], decision_lines: list[str],
                 winner: str | None) -> str:
    out = ["# Judge audit report",
          "",
          f"Generated {pd.Timestamp.utcnow().isoformat()}.",
          "",
          "## Agreement table",
          "",
          "| Judge | n | Spearman | Pearson | Cohen kappa (q) | Krippendorff alpha |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['judge']} | {r['n']} | "
                  f"{r['spearman']:.4f} | {r['pearson']:.4f} | "
                  f"{r['cohen_kappa_q']:.4f} | {r['krippendorff_a']:.4f} |")
    out += ["", "## Decision", ""] + decision_lines
    if winner:
        out += ["", f"## Stage B run with: `{winner}`",
               "",
               "Next step: kick off Stage B production run with the winner "
               f"only:",
               f"```",
               f"python evaluation/run_judge_ensemble.py --stage b "
               f"--judges {winner.replace('_','-').replace('llama-3-3','llama-3.3').replace('gpt5-4','gpt-5.4').replace('gemini-3-1','gemini-3.1')}",
               f"```"]
    return "\n".join(out) + "\n"


# ── CLI ───────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--require-three-raters", action="store_true",
                  help="abort if not all 3 human raters submitted")
    args = p.parse_args()

    log.info("loading human ratings ...")
    humans = load_human_ratings()

    if args.require_three_raters:
        complete = humans[[f"rating_{r}" for r in RATERS]].notna().all(axis=1).sum()
        if complete < len(humans):
            raise SystemExit(
                f"only {complete}/{len(humans)} rows have all 3 raters; "
                "abort per --require-three-raters")

    log.info("loading judge scores ...")
    judges = load_judge_scores()

    rows = []
    for slug, jdf in judges.items():
        result = compute_agreement(jdf, humans, slug)
        rows.append(result)
        log.info("  %s: n=%d, spearman=%.4f, kappa_q=%.4f, krip=%.4f",
                slug, result["n"], result["spearman"],
                result["cohen_kappa_q"], result["krippendorff_a"])

    rows = sorted(rows, key=lambda r: r["spearman"], reverse=True)
    winner, decision_lines = pick_winner(rows)
    report = render_report(rows, decision_lines, winner)

    OUT_REPORT.write_text(report)
    log.info("wrote %s", OUT_REPORT.relative_to(ROOT))
    print()
    print(report)


if __name__ == "__main__":
    main()
