import asyncio
import os
import re
import time

from google.genai import errors as genai_errors

from google import genai
from google.genai import types

from indexer import RepoIndexer
from models import Domain, Finding
from patterns import Pattern
from patterns.genomics import GENOMICS_PATTERNS
from rlt import build_causal_context, build_disk_causal_context


MODEL = "gemini-2.5-flash-lite"
MAX_OUTPUT_TOKENS = 500

_SYSTEM_INSTRUCTION = (
    "You are a scientific code reviewer specializing in genomics "
    "methodology bugs. You respond concisely. You never hallucinate "
    "findings. If you are not confident a bug is present, you answer NO."
)

_MULTI_FILE_SYSTEM_INSTRUCTION = (
    "You are a scientific code reviewer specializing in genomics methodology bugs. "
    "You respond concisely. You never hallucinate findings. "
    "If you are not confident a bug is present, you answer NO. "
    "Code spans multiple files separated by '=== FILE: <name> ===' headers. "
    "A CAUSAL FLOW ANALYSIS section may follow, showing how variables produced "
    "by key functions flow across files — use it to identify cross-file bugs. "
    "A DISK-LINK ANALYSIS section may follow, showing files written in one script "
    "and read in another — these represent data-flow connections invisible in the AST."
)

_PATTERNS_BY_DOMAIN: dict[Domain, list[Pattern]] = {
    "genomics": GENOMICS_PATTERNS,
    "neuroscience": [],
    "cardiac": [],
}

_CLASSIFIER_TRAINING_CALL = re.compile(
    r"\.fit\s*\(|"
    r"\bcross_val_score\s*\(|"
    r"\bcross_validate\s*\(|"
    r"\bGridSearchCV\s*\(|"
    r"\bRandomizedSearchCV\s*\(|"
    r"\.train\s*\(|"
    r"\.backward\s*\(|"
    r"\bSCVI\s*\(|"                 # scVI model instantiation
    r"\bSCANVI\s*\(|"               # scANVI model instantiation
    r"highly_variable_genes\s*\(|"  # HVG selection (pre-split embedding leakage)
    r"\bfit_transform\s*\("         # sklearn scalers/PCA fitted on full data
)


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and fill in your key."
        )
    return genai.Client(api_key=api_key)


def _parse_response(text: str, pattern: Pattern) -> Finding:
    first_word = re.match(r"\s*(YES|NO)\b", text, re.IGNORECASE)
    found = bool(first_word and first_word.group(1).upper() == "YES")

    explanation = text
    if first_word:
        explanation = text[first_word.end():].lstrip(" :,.-\n")

    line_ref_match = re.search(
        r"line[s]?\s*[:#]?\s*([0-9]+(?:\s*(?:,|and|-|to)\s*[0-9]+)*)",
        text,
        re.IGNORECASE,
    )
    line_reference = line_ref_match.group(0) if line_ref_match else ""

    cleaned = explanation.strip()
    if not cleaned:
        cleaned = "(no explanation returned)" if found else "No issue detected"

    return Finding(
        pattern_id=pattern.id,
        pattern_name=pattern.name,
        severity=pattern.severity,
        found=found,
        finding=cleaned,
        line_reference=line_reference,
        doc_link=pattern.doc_link,
    )


async def _run_pattern(
    client: genai.Client,
    code: str,
    pattern: Pattern,
    multi_file: bool = False,
) -> Finding:
    if pattern.id == "GEN-003" and not _CLASSIFIER_TRAINING_CALL.search(code):
        return Finding(
            pattern_id=pattern.id,
            pattern_name=pattern.name,
            severity=pattern.severity,
            found=False,
            finding=(
                "No classifier training step detected in the code. "
                "Feature-selection leakage requires both label-informed "
                "selection and a downstream model training call "
                "(e.g. .fit(), cross_val_score())."
            ),
            line_reference="",
            doc_link=pattern.doc_link,
        )

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=f"{pattern.detection_prompt}\n\nCODE TO ANALYZE:\n{code}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    _MULTI_FILE_SYSTEM_INSTRUCTION if multi_file else _SYSTEM_INSTRUCTION
                ),
                max_output_tokens=MAX_OUTPUT_TOKENS,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except genai_errors.ClientError as e:
        if e.status_code == 429:
            raise RuntimeError(
                "Gemini API rate limit reached (free tier: 250k tokens/min). "
                "Wait ~60 seconds and try again, or reduce the number of files "
                "uploaded at once (10–15 files is a safe batch size)."
            ) from e
        raise RuntimeError(f"Gemini API error: {e}") from e

    text = response.text or ""
    return _parse_response(text, pattern)


# ------------------------------------------------------------------
# Single-file analysis (original path — unchanged)
# ------------------------------------------------------------------

async def analyze(code: str, domain: Domain) -> tuple[list[Finding], float, int]:
    patterns = _PATTERNS_BY_DOMAIN.get(domain, [])
    if not patterns:
        return [], 0.0, 0

    client = _get_client()
    start = time.perf_counter()

    findings = list(
        await asyncio.gather(
            *(_run_pattern(client, code, p) for p in patterns)
        )
    )

    elapsed = time.perf_counter() - start
    return findings, elapsed, len(patterns)


# ------------------------------------------------------------------
# Multi-file analysis (new path)
# ------------------------------------------------------------------

def _build_full_context(files: dict[str, str]) -> str:
    parts = []
    for fname, content in files.items():
        parts.append(f"=== FILE: {fname} ===\n{content}")
    return "\n\n".join(parts)


async def analyze_files(
    files: dict[str, str], domain: Domain
) -> tuple[list[Finding], float, int]:
    patterns = _PATTERNS_BY_DOMAIN.get(domain, [])
    if not patterns:
        return [], 0.0, 0

    # Drop empty files (e.g. __init__.py) before indexing
    files = {k: v for k, v in files.items() if v.strip()}
    if not files:
        return [], 0.0, 0

    # Build symbol table
    indexer = RepoIndexer()
    indexer.index(files)
    repo_imports = indexer.get_imports()

    full_code = _build_full_context(files)

    # Inject disk-link analysis so all patterns see cross-script file flow
    disk_ctx = build_disk_causal_context(indexer)
    if disk_ctx:
        full_code = (
            f"{full_code}\n\n=== DISK-LINK ANALYSIS ===\n"
            "The following data-flow connections travel through files on disk "
            "(written in one script, read in another):\n"
            f"{disk_ctx}"
        )

    client = _get_client()
    start = time.perf_counter()

    tasks: list = []
    active_patterns: list[Pattern] = []

    for pattern in patterns:
        # Triage: skip if none of the required imports are present
        if pattern.trigger_imports and not any(
            imp in repo_imports for imp in pattern.trigger_imports
        ):
            continue

        active_patterns.append(pattern)

        # RLT: build causal context if pattern has seed functions
        code_for_pattern = full_code
        if pattern.seed_functions:
            causal_ctx = build_causal_context(
                indexer, list(pattern.seed_functions)
            )
            if causal_ctx:
                code_for_pattern = (
                    f"{full_code}\n\n=== CAUSAL FLOW ANALYSIS ===\n{causal_ctx}"
                )

        tasks.append(_run_pattern(client, code_for_pattern, pattern, multi_file=True))

    if not tasks:
        return [], 0.0, 0

    # For large file sets run patterns sequentially to stay within
    # the free-tier token-per-minute limit (250k tokens/min).
    # Small sets (≤5 files) run in parallel as before.
    large_repo = len(files) > 5
    if large_repo:
        findings = []
        for task in tasks:
            findings.append(await task)
    else:
        findings = list(await asyncio.gather(*tasks))

    elapsed = time.perf_counter() - start
    return findings, elapsed, len(active_patterns)
