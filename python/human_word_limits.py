#!/usr/bin/env python3
"""
human_word_limits.py - Human fact-preservation labels for the 20/40/60/80-word LLM summaries vs NLG and SWUM

Each word-limit annotation workbook (design_pattern_preservation_annotation_{20,40,60,80}w.xlsx) shows the
same 30 files and extracted facts as the default workbook (design_pattern_preservation_annotation.xlsx),
with the GPT and Mistral summaries of that word limit next to the unchanged NLG and SWUM summaries.
Every length-constrained variant is evaluated on its own and then compared with NLG and SWUM, whose
labels are taken from the default workbook only (the baseline summaries are identical in every
workbook, so their labels are reused rather than re-annotated).

Steps:
    1. Read the default workbook (NLG, SWUM and the default GPT/Mistral summaries) and every word-limit
       workbook, mapping the letters A-D to tools with evaluation-results/manual_annotation_key*.csv.
       A word-limit workbook is used only when all of its GPT/Mistral labels are filled in; otherwise
       it is listed as skipped. The script checks that every workbook has the same facts and the same
       NLG/SWUM summary texts as the default workbook.
    2. Join the labels to fact_preservation_word_limits_verdicts.csv for the fact category, fact type
       and summary length, checking that the fact texts match.
    3. Per tool: Preserved / Omitted / Incorrect rates over all facts and Preserved rate per category.
    4. Per variant: paired Wilcoxon signed-rank test of the per-file Preserved rate against NLG and
       against SWUM (30 files), with the matched-pairs rank-biserial effect size.

Inputs:
    design_pattern_preservation_annotation.xlsx              NLG/SWUM baseline and default GPT/Mistral
    design_pattern_preservation_annotation_{20,40,60,80}w.xlsx  word-limit GPT/Mistral
    evaluation-results/manual_annotation_key*.csv            letter -> tool for F01-F30
    evaluation-results/fact_preservation_word_limits_verdicts.csv  fact category, type, summary words

Outputs:
    evaluation-results/human_word_limits_labels.csv   one row per fact and summary (human label)
    evaluation-results/human_word_limits_rates.csv    label rates of each tool, overall and by category
    evaluation-results/human_word_limits_tests.csv    Wilcoxon tests, each variant vs NLG and vs SWUM
    evaluation-results/results.txt                    delimited block (replaced on re-run),
                                                      plain-text and LaTeX tables

Usage:
    .venv/bin/python python/human_word_limits.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy import stats

from calculate_wilcoxon_tests import effect_magnitude, rank_biserial_effect_size
from human_judge_agreement import EVAL_DIR, LABELS, LETTERS, REPO_ROOT, RESULTS_TXT, find_row

VERDICTS_CSV = EVAL_DIR / "fact_preservation_word_limits_verdicts.csv"
OUT_PREFIX = EVAL_DIR / "human_word_limits"

BLOCK_START = "<<<BEGIN HUMAN EVALUATION WORD LIMITS>>>"
BLOCK_END = "<<<END HUMAN EVALUATION WORD LIMITS>>>"

BASELINES = ["DPS_NLG", "DPS_SWUM"]
DEFAULT_LLMS = ["DPS_LLM (GPT)", "DPS_LLM (Mistral)"]
# (condition, workbook/key suffix)
WORD_LIMITS = [("20w", "_20w"), ("40w", "_40w"), ("60w", "_60w"), ("80w", "_80w")]
CATEGORIES = ["pattern role", "responsibility", "relationship", "identity"]
ALPHA = 0.05


# ----------------------------------------------------------------------------- workbooks

def read_workbook(suffix: str) -> Tuple[pd.DataFrame, Dict[Tuple[str, str], str]]:
    """Facts x letters with the human label, and the summary text of each (file, tool)."""
    path = REPO_ROOT / f"design_pattern_preservation_annotation{suffix}.xlsx"
    key = pd.read_csv(EVAL_DIR / f"manual_annotation_key{suffix}.csv", dtype=str)
    wb = load_workbook(path, data_only=True)
    rows, texts = [], {}
    for r in key.itertuples():
        ws = wb[r.file_id]
        first = find_row(ws, 1, "A", start=8)
        header = find_row(ws, 2, "Fact type", start=10)
        for i, L in enumerate(LETTERS):
            method = getattr(r, f"summary_{L}")
            assert ws.cell(first + i, 1).value == L, (path.name, r.file_id, L)
            texts[(r.file_id, method)] = ws.cell(first + i, 2).value
            row = header + 1
            while ws.cell(row, 1).value not in (None, "UC"):
                rows.append({
                    "file_id": r.file_id, "project": r.project, "design_pattern": r.design_pattern,
                    "file": r.file_name, "fact_id": int(float(ws.cell(row, 1).value)),
                    "fact_text_workbook": ws.cell(row, 3).value, "letter": L, "method": method,
                    "human": (ws.cell(row, 6 + i).value or "").strip().upper() or None,
                    "workbook": path.name,
                })
                row += 1
    return pd.DataFrame(rows), texts


def fact_set(df: pd.DataFrame) -> set:
    return set(df[["file_id", "fact_id", "fact_text_workbook"]].itertuples(index=False, name=None))


# ----------------------------------------------------------------------------- results.txt

def write_block(results_txt: Path, section: str) -> None:
    """Write the section into results.txt, replacing any previous block with the same markers."""
    existing = results_txt.read_text(encoding="utf-8") if results_txt.exists() else ""
    start, end = existing.find(BLOCK_START), existing.find(BLOCK_END)
    if start != -1 and end != -1:
        updated = existing[:start] + section + existing[end + len(BLOCK_END) + 1:]
    else:
        # blocks are separated by two blank lines
        updated = existing.rstrip("\n") + "\n\n\n" + section if existing else section
    results_txt.write_text(updated, encoding="utf-8")


def latex_table(rates: pd.DataFrame, tests: pd.DataFrame, n_files: int, n_facts: int) -> List[str]:
    def esc(s: str) -> str:
        return s.replace("_", r"\_")

    def eff(method: str, baseline: str) -> str:
        t = tests[(tests.method == method) & (tests.baseline == baseline)]
        if t.empty:
            return "--"
        t = t.iloc[0]
        return f"{t.effect_size_r:+.2f}{'*' if t.p_value < ALPHA else ''}"

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        rf"  \caption{{Human-annotated design-pattern fact preservation under word limits ({n_files} files, "
        rf"{n_facts} facts). $r$: rank-biserial effect size of the paired Wilcoxon test of the per-file "
        r"Preserved rate against NLG and SWUM (positive: the variant preserves more); * $p < 0.05$.}",
        r"  \label{tab:human-word-limits}",
        r"  \begin{tabular}{lrrrrrrrr}",
        r"    \toprule",
        r"    Corpus & Mean words & All & Pattern role & Responsibility & Relationship & Identity"
        r" & $r$ vs NLG & $r$ vs SWUM \\",
        r"    \midrule",
    ]
    for _, r in rates.iterrows():
        cats = " & ".join(f"{r[f'preserved_{c}']:.1%}" for c in CATEGORIES)
        lines.append(f"    {esc(r.method)} & {r.mean_words:.1f} & {r.preserved_rate:.1%} & {cats} & "
                     f"{eff(r.method, 'DPS_NLG')} & {eff(r.method, 'DPS_SWUM')} \\\\".replace("%", r"\%"))
        if r.method == BASELINES[-1]:
            lines.append(r"    \midrule")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    return lines


# ----------------------------------------------------------------------------- analysis

def main() -> None:
    out: List[str] = []

    def say(line: str = "") -> None:
        out.append(line)
        print(line)

    # --- labels
    base, base_texts = read_workbook("")
    assert base.human.isin(LABELS).all(), base[~base.human.isin(LABELS)]
    base["condition"] = np.where(base.method.isin(BASELINES), "baseline", "default")
    parts, status = [base], []
    for cond, suffix in WORD_LIMITS:
        df, texts = read_workbook(suffix)
        assert fact_set(df) == fact_set(base), f"{suffix}: facts differ from the default workbook"
        for (fid, method), text in texts.items():
            if method in BASELINES:
                assert text == base_texts[(fid, method)], f"{suffix} {fid} {method}: summary text differs"
        var = df[~df.method.isin(BASELINES)].copy()
        blank = int((~var.human.isin(LABELS)).sum())
        if blank:
            files = var[~var.human.isin(LABELS)].file_id.nunique()
            status.append(f"  {cond}: skipped, {blank} of {len(var)} GPT/Mistral labels blank ({files} files)")
            continue
        status.append(f"  {cond}: used, {len(var)} GPT/Mistral labels")
        var["condition"] = cond
        parts.append(var)
    labels = pd.concat(parts, ignore_index=True)

    verdicts = pd.read_csv(VERDICTS_CSV)
    merged = labels.merge(verdicts[["project", "design_pattern", "file", "method", "fact_id", "fact_text",
                                    "fact_type", "category", "summary_words"]],
                          on=["project", "design_pattern", "file", "method", "fact_id"],
                          how="left", validate="one_to_one")
    missing = merged.fact_text.isna().sum()
    text_mismatch = (merged.fact_text_workbook.str.strip() != merged.fact_text.str.strip()).sum()
    assert missing == 0 and text_mismatch == 0, (missing, text_mismatch)
    df = merged.drop(columns="fact_text_workbook")
    df[["condition", "method", "file_id", "project", "design_pattern", "file", "fact_id", "fact_type",
        "category", "fact_text", "letter", "summary_words", "human", "workbook"]].to_csv(
        f"{OUT_PREFIX}_labels.csv", index=False)

    methods = BASELINES + DEFAULT_LLMS + [m for c, _ in WORD_LIMITS
                                          for m in sorted(df[df.condition == c].method.unique())]
    n_files = df.file_id.nunique()
    n_facts = df.groupby(["file_id", "fact_id"]).ngroups

    say("=" * 78)
    say("HUMAN EVALUATION UNDER WORD LIMITS (fact preservation: variants vs NLG and SWUM)")
    say("=" * 78)
    say(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"Files: {n_files}   facts: {n_facts}   (same files and facts in every workbook)")
    say("NLG and SWUM labels: design_pattern_preservation_annotation.xlsx (the baseline summaries are")
    say("identical in every workbook, so they are labelled once and reused for every comparison).")
    say("Default GPT/Mistral: design_pattern_preservation_annotation.xlsx")
    say("Word-limit workbooks (used only when every GPT/Mistral label is filled in):")
    for line in status:
        say(line)
    say(f"Fact categories and summary words: {VERDICTS_CSV.name}; all {len(df)} labels matched, fact texts identical.")
    say()

    # --- rates
    summ = (df.assign(p=df.human == "PRESERVED")
              .groupby(["condition", "method", "file_id"], as_index=False)
              .agg(preserved_rate=("p", "mean"), summary_words=("summary_words", "first")))
    rate_rows = []
    for m in methods:
        sub = df[df.method == m]
        row = {"condition": sub.condition.iloc[0], "method": m, "files": sub.file_id.nunique(), "facts": len(sub),
               "mean_words": float(summ[summ.method == m].summary_words.mean())}
        for lab in LABELS:
            row[lab.lower()] = int((sub.human == lab).sum())
            row[f"{lab.lower()}_rate"] = float((sub.human == lab).mean())
        row["macro_preserved_rate"] = float(summ[summ.method == m].preserved_rate.mean())
        for c in CATEGORIES:
            row[f"preserved_{c}"] = float((sub[sub.category == c].human == "PRESERVED").mean())
        rate_rows.append(row)
    rates = pd.DataFrame(rate_rows)
    rates.to_csv(f"{OUT_PREFIX}_rates.csv", index=False, float_format="%.4f")

    cat_n = df[df.method == BASELINES[0]].category.value_counts()
    say("1. Human labels by tool (micro: share of all facts)")
    say("-" * 78)
    say(f"{'Corpus':<19}{'Cond.':<9}{'Words':>6}{'Preserved':>10}{'Omitted':>9}{'Incorrect':>10}"
        + "".join(f"{c[:12]:>13}" for c in CATEGORIES))
    for _, r in rates.iterrows():
        say(f"{r.method:<19}{r.condition:<9}{r.mean_words:>6.1f}{r.preserved_rate:>10.1%}{r.omitted_rate:>9.1%}"
            f"{r.incorrect_rate:>10.1%}" + "".join(f"{r[f'preserved_{c}']:>13.1%}" for c in CATEGORIES))
    say("Facts per tool: " + ", ".join(f"{c} {cat_n.get(c, 0)}" for c in CATEGORIES) + f", all {n_facts}")
    say("Macro (mean of per-file rates): " + "; ".join(
        f"{r.method} {r.macro_preserved_rate:.1%}" for _, r in rates.iterrows()))
    say()

    # --- tests
    wide = summ.pivot(index="file_id", columns="method", values="preserved_rate")
    test_rows = []
    for m in methods:
        if m in BASELINES:
            continue
        for b in BASELINES:
            x, y = wide[m].to_numpy(), wide[b].to_numpy()
            diffs = x - y
            row = {"condition": rates.set_index("method").condition[m], "method": m, "baseline": b,
                   "n_pairs": len(diffs), "mean_method": float(x.mean()), "mean_baseline": float(y.mean()),
                   "median_diff": float(np.median(diffs)), "wins": int((diffs > 0).sum()),
                   "ties": int((diffs == 0).sum()), "losses": int((diffs < 0).sum())}
            if np.allclose(diffs, 0.0):
                row.update(w_statistic=0.0, p_value=1.0, effect_size_r=0.0)
            else:
                res = stats.wilcoxon(x, y, alternative="two-sided")
                row.update(w_statistic=float(res.statistic), p_value=float(res.pvalue),
                           effect_size_r=rank_biserial_effect_size(diffs))
            row["effect_magnitude"] = effect_magnitude(row["effect_size_r"])
            row["significant"] = row["p_value"] < ALPHA
            test_rows.append(row)
    tests = pd.DataFrame(test_rows)
    tests.to_csv(f"{OUT_PREFIX}_tests.csv", index=False, float_format="%.4f")

    say(f"2. Paired Wilcoxon signed-rank tests on the per-file Preserved rate ({n_files} files)")
    say("-" * 78)
    say("Two-sided; r = matched-pairs rank-biserial (W+ - W-) / (W+ + W-), positive = the variant")
    say(f"preserves more than the baseline. W/T/L = files where the variant is higher / tied / lower. alpha = {ALPHA}")
    say()
    say(f"{'Comparison':<32}{'Mean':>14}{'Median d':>10}{'W/T/L':>10}{'W':>8}{'p':>10}{'r':>8}  Effect")
    for _, t in tests.iterrows():
        say(f"{t.method + ' vs ' + t.baseline:<32}{t.mean_method:>7.1%}{t.mean_baseline:>7.1%}"
            f"{t.median_diff:>+10.3f}{f'{t.wins}/{t.ties}/{t.losses}':>10}{t.w_statistic:>8.1f}"
            f"{t.p_value:>10.3g}{t.effect_size_r:>+8.2f}  {t.effect_magnitude}{' *' if t.significant else ''}")
    say("(Mean = mean per-file Preserved rate of the variant and of the baseline; * p < alpha)")
    say()

    for line in latex_table(rates, tests, n_files, n_facts):
        say(line)
    write_block(RESULTS_TXT, "\n".join([BLOCK_START, *out, BLOCK_END]) + "\n")


if __name__ == "__main__":
    main()
