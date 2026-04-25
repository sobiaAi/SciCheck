from __future__ import annotations

import os
from dataclasses import dataclass, field

from indexer import RepoIndexer


@dataclass
class Lineage:
    seed: str
    all_names: set[str] = field(default_factory=set)
    assignments: list[dict] = field(default_factory=list)
    usages: list[dict] = field(default_factory=list)


def trace(indexer: RepoIndexer, seed_var: str, max_depth: int = 3) -> Lineage:
    """Recursively traces all aliases and consumption sites of seed_var."""
    lineage = Lineage(seed=seed_var)
    _expand(indexer, seed_var, lineage, depth=0, max_depth=max_depth)
    return lineage


def _expand(
    indexer: RepoIndexer,
    var_name: str,
    lineage: Lineage,
    depth: int,
    max_depth: int,
) -> None:
    if depth > max_depth or var_name in lineage.all_names:
        return
    lineage.all_names.add(var_name)

    for a in indexer.get_var_assignments(var_name):
        lineage.assignments.append(a)

    for u in indexer.get_var_usages(var_name):
        lineage.usages.append(u)

    for alias in indexer.get_aliases(var_name):
        _expand(indexer, alias, lineage, depth + 1, max_depth)


def build_causal_context(
    indexer: RepoIndexer,
    seed_functions: list[str],
    max_depth: int = 3,
) -> str:
    """
    For each seed function (e.g. 'removeBatchEffect'), find every variable it
    produces, trace those variables across the repo via RLT, and return a
    structured context block for injection into the LLM prompt.
    """
    parts: list[str] = []

    for func in seed_functions:
        produced = indexer.get_produced_by(func)
        for item in produced:
            var_name = item["var_name"]
            lineage = trace(indexer, var_name, max_depth)

            if not lineage.usages:
                continue

            parts.append(f"\n--- Causal Chain: {func}() → '{var_name}' ---")
            parts.append(
                f"Origin ({item['file']}:{item['line']}): {item['snippet']}"
            )
            for usage in lineage.usages:
                parts.append(
                    f"  Consumed by {usage['func_name']}() "
                    f"({usage['file']}:{usage['line']}): {usage['snippet']}"
                )
            if len(lineage.all_names) > 1:
                aliases = lineage.all_names - {var_name}
                parts.append(f"  Aliases traced: {', '.join(sorted(aliases))}")

    return "\n".join(parts)


def build_disk_causal_context(indexer: RepoIndexer) -> str:
    """
    Matches file writes in one script to file reads in another by basename.
    Returns a context block describing cross-script data flow via disk.
    """
    writes = indexer.get_file_writes()
    reads = indexer.get_file_reads()
    if not writes or not reads:
        return ""

    def norm(p: str) -> str:
        return os.path.basename(p).lower()

    write_map: dict[str, list[dict]] = {}
    for w in writes:
        write_map.setdefault(norm(w["path_arg"]), []).append(w)

    parts: list[str] = []
    seen: set[tuple] = set()
    for r in reads:
        key = norm(r["path_arg"])
        for w in write_map.get(key, []):
            pair = (w["file"], w["line"], r["file"], r["line"])
            if pair in seen:
                continue
            seen.add(pair)
            parts.append(
                f"\n--- Disk Link: '{key}' ---"
            )
            parts.append(f"  Written in {w['file']}:{w['line']}  ->  {w['snippet']}")
            parts.append(f"  Read    in {r['file']}:{r['line']}  ->  {r['snippet']}")

    return "\n".join(parts)
