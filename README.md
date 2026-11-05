# Design Pattern Summariser

An automated platform that generates, ranks and evaluates natural-language summaries of Java
design-pattern implementations. Three summarisation strategies are compared against 150
human-written reference summaries: template-driven NLG, identifier-aware SWUM, and LLMs
(a GPT model and a Mistral model, both called through OpenRouter). The comparison uses
automated similarity metrics, an LLM judge and a manual annotation study.

## Overview

The pipeline analyses curated Java projects that implement nine Gang-of-Four patterns and
produces one summary per class with each of three methods:

1. **NLG (Natural Language Generation)**: deterministic templates driven by the AST and by
   design-pattern detection.
2. **SWUM (Software Word Use Model)**: linguistic modelling of identifier names plus
   lightweight static analysis.
3. **LLM (Large Language Model)**: a GPT model and a Mistral model on OpenRouter, prompted with
   the class's code features. Both are run with a concise 50-word prompt, a non-concise
   50-word prompt and 20/40/60/80-word length variants.

The summaries are then evaluated in four ways:

- **Similarity to the human references**: cosine similarity and BERTScore.
- **LLM-judge ranking**: the four default summaries of each class (NLG, GPT, Mistral, SWUM) are
  ranked on five criteria.
- **Fact preservation**: an LLM judge checks which design-pattern facts, extracted from the code,
  each summary preserves, omits or gets wrong.
- **Human annotation**: a manual annotation of 30 files is used to measure agreement with the LLM
  judge and to evaluate the length variants.

## Repository Layout

```text
<repository-root>/
├── src/main/java/
│   ├── common/              # Shared AST parsing, path helpers and pattern detection
│   ├── dps_nlg/             # NLG generator               (mvn exec:java@nlg)
│   ├── dps_swum/            # SWUM-based summariser        (mvn exec:java@swum)
│   └── dps_llm/             # OpenRouter client and prompts (mvn exec:java@llm-*)
├── src/test/java/           # JUnit 5 tests
├── python/                  # Evaluation, ranking and statistics scripts
├── resources/               # prompts.json, shared by the Java and Python code
├── input/
│   ├── corpus/              # Java sources: <Project>/<Pattern>/*.java (150 files)
│   └── ground-truth/        # Human references (DPS_Human_Summaries.csv)
├── output/
│   ├── json-output/         # Per-project/pattern JSON intermediates (nlg/, swum/, llm/)
│   └── summary-output/      # Generated summaries, one CSV per method and prompt
├── annotations/             # Manual fact-preservation annotation workbooks (.xlsx)
├── evaluation-results/      # Metrics, rankings, statistical tests and results.txt
├── pom.xml
├── requirements.txt
├── LICENSE
└── README.md
```

## Prerequisites

- **Java**: JDK 11 or later (the code compiles to Java 11).
- **Maven**: 3.6 or later.
- **Python**: 3.10 or later.
- **OpenRouter API key**: needed only to generate LLM summaries and to run the two LLM-judge
  scripts (`rank_summaries_four_way.py`, `judge_fact_preservation.py`). Everything else runs
  offline.

## Where to run the commands from

**Run every command in this README from the repository root**, the folder that contains
`pom.xml`, `.env` and `python/`. Do not `cd` into `python/` or `src/`. The Java pipelines and
some Python defaults use paths relative to the current folder, such as `input/corpus/` and
`output/summary-output/`.

To check you are in the right place:

```bash
ls pom.xml python/ input/corpus/    # all three should be listed
```

## Setup (one time)

### 1) Get the code and build the Java code

Download and extract the anonymised artefact, then build it from the repository root:

```bash
cd <repository-root>
mvn clean install        # compiles the code and runs the JUnit tests
```

### 2) Create and activate a Python virtual environment

Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows Command Prompt:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` installs the CPU build of PyTorch. On a machine with an NVIDIA GPU, remove
the `--extra-index-url` line first.

The two human-annotation scripts (`human_judge_agreement.py`, `human_word_limits.py`) also need
`openpyxl`, which is not in `requirements.txt`:

```bash
python -m pip install openpyxl
```

Activate the environment again in every new terminal before you run the Python scripts.

### 3) Create `.env` in the repository root

The Java pipelines and the Python scripts both read `.env` from the repository root. It is
listed in `.gitignore`, so your key is not committed. Values may be wrapped in quotes.

Fill in only the sections for the steps you plan to run:

```text
# --- Shared -------------------------------------------------------------------
OPENROUTER_API_KEY=sk-your-key
OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions

# --- Java LLM summary generation (mvn exec:java@llm-*) ------------------------
OPENROUTER_MAX_COMPLETION_TOKENS=512
OPENROUTER_TEMPERATURE=0
# OpenRouter model ids; the --gpt / --mistral flag picks which one a run uses
GPT_MODEL=openai/your-gpt-model-id
MISTRAL_MODEL=mistralai/your-mistral-model-id
# Optional: summarise only the first N projects
LLM_PROJECT_LIMIT=
# Optional: write the summaries to this CSV instead of the default for the run
LLM_SUMMARY_PATH=
# Optional: run other prompt aliases; leave empty for the length-variant executions
LLM_PROMPT_ALIASES=

# --- LLM-judge ranking (rank_summaries_four_way.py); required, no defaults -----
RANK_SUMMARIES_MODEL=your-judge-model-id
RANK_SUMMARIES_MAX_TOKENS=50
# Optional: separate endpoint for ranking; defaults to OPENROUTER_API_URL
RANK_SUMMARIES_API_URL=

# --- Fact-preservation judge (judge_fact_preservation.py); required, no defaults
FACT_JUDGE_MODEL=your-judge-model-id
FACT_JUDGE_TEMPERATURE=0
FACT_JUDGE_TOKENS_PER_FACT=
FACT_JUDGE_MAX_TOKENS=
FACT_JUDGE_MAX_ATTEMPTS=
FACT_JUDGE_REQUEST_TIMEOUT_SECONDS=
FACT_JUDGE_RETRY_BACKOFF_SECONDS=
FACT_JUDGE_MAX_ROLE_FACTS=
FACT_JUDGE_MAX_FIELD_FACTS=
FACT_JUDGE_MAX_CONSTRUCTOR_FACTS=
FACT_JUDGE_MAX_METHOD_FACTS=
FACT_JUDGE_MAX_CALL_FACTS=
# Optional: separate endpoint for this judge; defaults to OPENROUTER_API_URL
FACT_JUDGE_API_URL=
```

The Java client retries rate-limit (429) and server (5xx) errors up to four times with
exponential backoff. `OPENROUTER_MAX_TOKENS` is still accepted when
`OPENROUTER_MAX_COMPLETION_TOKENS` is not set (the default is 256). `OPENROUTER_MODEL` is no
longer read.

## Running the pipeline

Run the steps in this order, because each one reads what the previous one wrote. All generated
summaries and evaluation results are already committed, so you can also start at any step.

The Maven commands are the same on Windows, Linux and macOS. On Windows you can use `py`
instead of `python`.

### Step 1: Generate summaries (Java)

```bash
# 1a. NLG summaries          -> output/summary-output/nlg_summaries.csv, output/json-output/nlg/
mvn exec:java@nlg

# 1b. SWUM summaries         -> output/summary-output/swum_summaries.csv, output/json-output/swum/
#     Reads output/json-output/nlg/, so run 1a first.
mvn exec:java@swum

# 1c. LLM summaries with the concise 50-word prompt (calls OpenRouter; needs .env)
mvn exec:java@llm-gpt        # GPT_MODEL     -> output/summary-output/llm_summaries_gpt.csv
mvn exec:java@llm-mistral    # MISTRAL_MODEL -> output/summary-output/llm_summaries_mistral.csv

# 1d. The same two models with the non-concise 50-word prompt
mvn exec:java@llm-gpt-nonconcise       # -> output/summary-output/llm_summaries_nonconcise_gpt.csv
mvn exec:java@llm-mistral-nonconcise   # -> output/summary-output/llm_summaries_nonconcise_mistral.csv

# 1e. Summary-length variants (20, 40, 60 or 80 words), one prompt per command
mvn exec:java@llm-gpt-20       # -> output/summary-output/llm_summaries_gpt_20.csv
mvn exec:java@llm-gpt-40       # -> output/summary-output/llm_summaries_gpt_40.csv
mvn exec:java@llm-gpt-60       # -> output/summary-output/llm_summaries_gpt_60.csv
mvn exec:java@llm-gpt-80       # -> output/summary-output/llm_summaries_gpt_80.csv
mvn exec:java@llm-mistral-20   # -> output/summary-output/llm_summaries_mistral_20.csv
mvn exec:java@llm-mistral-40   #    ... and so on for 40, 60 and 80
mvn exec:java@llm-mistral-60
mvn exec:java@llm-mistral-80

# Optional: print the available prompts
mvn exec:java@prompt-demo
```

#### Resuming an interrupted LLM run

A normal LLM run empties its CSV first. If a run stops part-way (for example because of 429
rate limits), use the matching `-resume` execution. It keeps the rows already in the CSV, skips
those classes without calling the API, and appends only the missing ones:

```bash
mvn exec:java@llm-gpt-resume
mvn exec:java@llm-mistral-resume
mvn exec:java@llm-gpt-nonconcise-resume
mvn exec:java@llm-mistral-nonconcise-resume
mvn exec:java@llm-gpt-20-resume        # every length variant has one, e.g. llm-mistral-80-resume
```

A class whose request fails still gets no row, so repeat the resume command until the run
reports `Failed summaries: 0` (and `Already in CSV` + `Summaries generated` = 150).

#### How the `llm-*` executions work

Each `llm-*` execution is a shortcut for running `DpsLlmApplication` with flags. Each pair below
is equivalent:

```bash
mvn exec:java@llm-gpt
mvn exec:java@llm-summaries -Dexec.args="--gpt"

mvn exec:java@llm-mistral-nonconcise
mvn exec:java@llm-summaries -Dexec.args="--mistral --nonconcise"

mvn exec:java@llm-mistral-resume
mvn exec:java@llm-summaries -Dexec.args="--mistral --resume"

mvn exec:java@llm-gpt-20
mvn exec:java@llm-summaries -Dexec.args="--gpt" -Dllm.prompt.aliases=SENIOR_ANALYST_20_WORDS
```

- Exactly one of `--gpt` or `--mistral` is required (`-gpt` and `-mistral` also work). Without
  one, the program prints its usage and exits. The flag selects the model id from `GPT_MODEL`
  or `MISTRAL_MODEL` in `.env`.
- `--nonconcise` switches the prompt from `SENIOR_ANALYST_50_WORDS` to
  `SENIOR_ANALYST_50_WORDS_NON_CONCISE`.
- The length variants set the JVM property `llm.prompt.aliases` to
  `SENIOR_ANALYST_<n>_WORDS`. Leave `LLM_PROMPT_ALIASES` in `.env` empty for these runs, because
  a value there takes precedence over the property.
- Each model and prompt combination writes its own CSV, so no run overwrites another. Set
  `LLM_SUMMARY_PATH` in `.env` to write somewhere else.

### Step 2: Similarity to the human references (offline)

```bash
python python/evaluate_summaries.py
```

This computes cosine similarity and BERTScore against the human summaries for NLG, SWUM, GPT,
Mistral, GPT non-concise and Mistral non-concise. A missing CSV is skipped. The first run
downloads the BERTScore model from Hugging Face, so it needs internet access once.

It writes the following to `evaluation-results/`:

- `nlg_vs_human_*.csv`, `swum_vs_human_*.csv`, `llm (gpt)_vs_human_*.csv`,
  `llm (mistral)_vs_human_*.csv`, `llm (gpt non-concise)_vs_human_*.csv` and
  `llm (mistral non-concise)_vs_human_*.csv` (class and project scores);
- `overall_comparison.csv`, `evaluation_summary.txt`, `results.txt` and
  `methods_comparison_violin_plots.png`.

**This script rewrites `results.txt` from scratch**, so run it before the scripts in steps 3
to 5, which add their own blocks to that file.

Useful options:

- `--gpt-csv`, `--mistral-csv`, `--gpt-nonconcise-csv`, `--mistral-nonconcise-csv`: score other
  files.
- `--skip-gpt-mistral`: leave the GPT and Mistral runs out.
- `--dps-llm-csv`, `--dps-llm-nonconcise-csv`: also score an extra LLM corpus.
- `--output-dir`: write the results to another folder.

The script warns when a CSV matches fewer than all 150 human summaries. If that happens, resume
that LLM run first.

### Step 3: LLM-judge ranking (needs API access)

```bash
# Rank NLG vs GPT vs Mistral vs SWUM on 5 criteria -> evaluation-results/four_way_ranking_*.csv
python python/rank_summaries_four_way.py

# Cheap trial on the first 3 classes (15 judge calls)
python python/rank_summaries_four_way.py --limit 3

# No API calls: re-score the replies saved in four_way_ranking_detail.csv
python python/rank_summaries_four_way.py --reparse

# As --reparse, then ask the judge once more for each reply that is still invalid
python python/rank_summaries_four_way.py --retry-invalid
```

For every class, the judge sees the human summary and the four generated summaries in the fixed
order 1 = NLG, 2 = GPT, 3 = Mistral, 4 = SWUM. It ranks them on accuracy, conciseness, adequacy,
code context and design-pattern recognition, using the `summary_ranking` prompts in
`resources/prompts.json`. Points per criterion are 1st = 4, 2nd = 3, 3rd = 2 and 4th = 1. A reply
that is not a full ranking of the four is recorded as invalid and earns no points.

The script writes the following to `evaluation-results/`:

- `four_way_ranking_detail.csv`: one row per class, saved after every class.
- `four_way_ranking_summary.csv`: 1st to 4th counts, mean rank and mean points per criterion.
- `four_way_ranking_head_to_head.csv`: how often each method in a pair was ranked higher.
- A block in `results.txt` with plain-text and LaTeX tables, replaced on every re-run.

### Step 4: Fact preservation (needs API access)

```bash
python python/judge_fact_preservation.py --dry-run     # extract and check the facts only, no API calls
python python/judge_fact_preservation.py --limit 3     # trial run on the first 3 classes
python python/judge_fact_preservation.py               # judge every class
python python/judge_fact_preservation.py --reparse     # no API calls: rebuild outputs from saved replies
python python/judge_fact_preservation.py --corpora word-limits   # add the 20/40/60/80-word summaries
```

For every class, atomic facts about its design-pattern role and relationships are extracted
from `output/json-output/nlg/`. An LLM judge then labels each fact as PRESERVED, OMITTED or
INCORRECT for each summary, using the `fact_preservation` prompt in `resources/prompts.json`.
Every reply is cached in `fact_preservation_raw.jsonl`, so a re-run with the same settings does
not call the API again.

Outputs are written to `evaluation-results/fact_preservation_{facts,verdicts,detail,summary,results}.csv`
plus a block in `results.txt`. With `--corpora word-limits`, the outputs are named
`fact_preservation_word_limits_*.csv` instead. See the script's docstring for the fact types and
the evidence checks.

### Step 5: Statistical tests and descriptive statistics (offline)

```bash
# Paired Wilcoxon tests and rank-biserial effect sizes: NLG and SWUM vs GPT, GPT non-concise,
# Mistral and Mistral non-concise (reads the *_vs_human_class_scores.csv files from step 2)
python python/calculate_wilcoxon_tests.py

# Friedman tests across the 5 ranking criteria, with post-hoc comparisons
# (reads four_way_ranking_detail.csv from step 3)
python python/friedman_test.py

# Words and characters per summary for every summary set, including the human references
python python/summary_length_stats.py
```

Each script writes its own block to `results.txt` and replaces that block when you run it
again.

### Step 6: Human annotation analysis (offline)

The `annotations/` folder holds the completed manual annotation workbooks:

- `design_pattern_preservation_annotation.xlsx`: 30 files with NLG, SWUM, GPT and Mistral
  summaries.
- `design_pattern_preservation_annotation_{20,40,60,80}w.xlsx`: the same files and facts, with
  the GPT and Mistral summaries of each word limit.

The summaries in each workbook are anonymised as A to D. The `evaluation-results/manual_annotation_key*.csv`
files map each letter back to its tool.

**The scripts look for the workbooks in the repository root, not in `annotations/`.** Copy them
there before you run the scripts:

```bash
cp annotations/*.xlsx .     # Windows: copy annotations\*.xlsx .

# Agreement between the human annotator and the fact-preservation judge (step 4)
python python/human_judge_agreement.py

# Human labels for the 20/40/60/80-word summaries, compared with NLG and SWUM
python python/human_word_limits.py
```

`human_judge_agreement.py` reports percentage agreement, Cohen's kappa and Gwet's AC1, with
bootstrap confidence intervals. It writes `human_judge_agreement_*.csv` and a de-anonymised copy
of the workbook. `human_word_limits.py` writes `human_word_limits_{labels,rates,tests}.csv`. Both
add a block to `results.txt`.

### Full run, copy and paste

From the repository root, with the virtual environment active and `.env` filled in:

```bash
mvn clean install
mvn exec:java@nlg
mvn exec:java@swum
mvn exec:java@llm-gpt
mvn exec:java@llm-mistral
mvn exec:java@llm-gpt-nonconcise
mvn exec:java@llm-mistral-nonconcise
for n in 20 40 60 80; do mvn exec:java@llm-gpt-$n; mvn exec:java@llm-mistral-$n; done
python python/evaluate_summaries.py
python python/rank_summaries_four_way.py
python python/judge_fact_preservation.py
python python/judge_fact_preservation.py --corpora word-limits
python python/calculate_wilcoxon_tests.py
python python/friedman_test.py
python python/summary_length_stats.py
cp annotations/*.xlsx .
python python/human_judge_agreement.py
python python/human_word_limits.py
```

The `for` loop is bash syntax. On Windows, run the eight length-variant commands one at a time.

### Script reference

| Script / command | API key | Reads | Writes (under `evaluation-results/` unless noted) |
| --- | --- | --- | --- |
| `mvn exec:java@nlg` | no | `input/corpus/` | `output/summary-output/nlg_summaries.csv`, `output/json-output/nlg/` |
| `mvn exec:java@swum` | no | `output/json-output/nlg/` | `output/summary-output/swum_summaries.csv`, `output/json-output/swum/`, `pipeline_summary.txt` |
| `mvn exec:java@llm-{gpt,mistral}` | yes | `input/corpus/`, `resources/prompts.json` | `output/summary-output/llm_summaries_{gpt,mistral}.csv` |
| `mvn exec:java@llm-{gpt,mistral}-nonconcise` | yes | the same | `output/summary-output/llm_summaries_nonconcise_{gpt,mistral}.csv` |
| `mvn exec:java@llm-{gpt,mistral}-{20,40,60,80}` | yes | the same | `output/summary-output/llm_summaries_{gpt,mistral}_<n>.csv` |
| `mvn exec:java@llm-...-resume` | yes (missing classes only) | the same, plus the existing CSV | appends to the same CSV |
| `evaluate_summaries.py` | no | summary CSVs, human CSV | `*_vs_human_{class,project}_scores.csv`, `overall_comparison.csv`, `evaluation_summary.txt`, `results.txt` (rewritten), violin plot |
| `rank_summaries_four_way.py` | yes | NLG, GPT, Mistral, SWUM CSVs, human CSV, `resources/prompts.json` | `four_way_ranking_{detail,summary,head_to_head}.csv`, block in `results.txt` |
| `judge_fact_preservation.py` | yes (not with `--dry-run` / `--reparse`) | `output/json-output/nlg/`, summary CSVs, `resources/prompts.json` | `fact_preservation_*.csv`, `fact_preservation_raw.jsonl`, block in `results.txt` |
| `calculate_wilcoxon_tests.py` | no | `*_vs_human_class_scores.csv` | block in `results.txt` |
| `friedman_test.py` | no | `four_way_ranking_detail.csv` | block in `results.txt` |
| `summary_length_stats.py` | no | all summary CSVs, human CSV | `summary_length_stats.csv`, block in `results.txt` |
| `human_judge_agreement.py` | no | annotation workbook (repo root), `manual_annotation_key.csv`, `fact_preservation_verdicts.csv` | `human_judge_agreement_*.csv`, de-anonymised workbook (repo root), block in `results.txt` |
| `human_word_limits.py` | no | annotation workbooks (repo root), `manual_annotation_key*.csv`, `fact_preservation_word_limits_verdicts.csv` | `human_word_limits_*.csv`, block in `results.txt` |
| `spearman_sensitivity_analysis.py` | no | `multi_criteria_rankings.csv` | console; `results.txt` with `--append-to` |

`python/project_paths.py` is a shared module, not a script.

`spearman_sensitivity_analysis.py` is left over from the earlier three-way ranking. Its input,
`multi_criteria_rankings.csv`, is no longer produced, so it cannot run until it is updated to
read `four_way_ranking_detail.csv`.

## Run from an IDE (VS Code, IntelliJ, Eclipse)

Set the run configuration's **working directory to the repository root**. This is the default
in VS Code when the repository folder is opened as the workspace, and `$PROJECT_DIR$` in
IntelliJ. With `python/` or `src/` as the working directory, the relative paths fail.

Java main classes:

- `src/main/java/dps_nlg/Application.java` (NLG)
- `src/main/java/dps_swum/swum/SWUMEvaluationPipeline.java` (SWUM)
- `src/main/java/dps_llm/DpsLlmApplication.java` (LLM): set the program arguments to `--gpt` or
  `--mistral`, plus `--nonconcise` or `--resume` if needed.

Python scripts: open any script from the table above and run it directly (in VS Code, use Run
Python File) with the `.venv` interpreter selected.

## Input Data

- **Human references**: 150 manually written summaries in
  `input/ground-truth/DPS_Human_Summaries.csv`.
- **Source code**: 150 Java files from three projects, under `input/corpus/<Project>/<Pattern>/`:
  `AbdurRKhalid`, `JamesZBL` and `SpringFramework`.
- **Prompts**: `resources/prompts.json` holds the summarisation prompts (`llm_summarization`), the
  ranking prompts (`summary_ranking`) and the fact-preservation prompt (`fact_preservation`). The
  Java LLM pipeline (on the classpath via `pom.xml`) and the Python judge scripts share it.
- The input paths are defined once, in `common.utils.ProjectPaths` (Java) and
  `python/project_paths.py` (Python). Add a new project as `input/corpus/<Project>/<Pattern>/`.

### Naming conventions

Every project uses the same nine pattern folders, written in PascalCase with no spaces or
hyphens: `AbstractFactory`, `Adapter`, `Decorator`, `Facade`, `FactoryMethod`, `Memento`,
`Observer`, `Singleton`, `Visitor`. The same form is used in:

- the `Design Pattern` column of the human CSV;
- the `Folder Name` column of every summary CSV;
- JSON file names and JSON pattern keys (see `common.designpatternidentifier.PatternNames`).

Inside summary sentences the readable form is used ("Abstract Factory pattern"), matching the
human references. The `URL` column of the human CSV, and the `project_path` column derived from
it, keep the original repositories' folder names (for example `JamesZBL/abstract-factory`).

Project names follow the same rule (`AbdurRKhalid`, `JamesZBL`, `SpringFramework`) in the input
folders, the `Project` column of every CSV, JSON file names and the evaluation tables. The Python
matchers ignore case and punctuation, so older labels such as `spring-framework` still match.

### Matching files across corpora

Twenty files share a (project, file name) pair with another file. For example, `Test.java`
appears seven times under AbdurRKhalid and `Application.java` nine times under JamesZBL. A
project-plus-file-name key would therefore merge different classes. Every matcher keys on
project + pattern folder + file name, and checks that the resulting keys are unique.

## Outputs

- `output/json-output/{nlg,swum,llm}/`: intermediate AST and metadata per project and pattern.
- `output/summary-output/*.csv`: generated summaries.
- `evaluation-results/*.csv`: per-class scores, rankings, verdicts and statistics.
- `evaluation-results/results.txt`: every script's tables in one file, in plain text and LaTeX,
  each in a delimited block.
- `evaluation-results/reviewer_feedback_fact_preservation_notes.md`: notes on the
  fact-preservation evaluation.

## Python dependencies

The key packages in `requirements.txt` are:

- `pandas`, `numpy`, `scikit-learn`: tabular processing and cosine similarity.
- `bert-score`, `transformers`, `torch`: BERTScore.
- `scipy`: statistical tests.
- `matplotlib`, `seaborn`: plots.
- `requests`, `python-dotenv`: API calls and `.env` loading.

`openpyxl` is also needed for the annotation scripts (see [Setup step 2](#2-create-and-activate-a-python-virtual-environment)).

## Design Patterns Covered

- **Creational**: Factory Method, Abstract Factory, Singleton.
- **Structural**: Adapter, Decorator, Facade.
- **Behavioural**: Observer, Visitor, Memento.

## Development Workflow

- `mvn clean compile`: compile the Java sources.
- `mvn test`: run the Java unit tests (JUnit 5, under `src/test/java`).

## Licence

Released under the [BSD 2-Clause Licence](LICENSE).

## Contact

Author details have been removed for anonymous review.

**Last updated**: 5 November 2026. Status: active research prototype.
