#!/usr/bin/env python3
"""Propose skill categories via TF-IDF + agglomerative hierarchical clustering.

Reads all skill SKILL.md frontmatters from .claude/skill-bank/ (or .claude/skills/
as fallback), builds TF-IDF vectors from name + description text, computes cosine
similarity, and runs average-linkage agglomerative clustering to propose category
groupings.

Use --apply to write `category: {label}` into each skill's YAML frontmatter.

Pure stdlib — zero external dependencies.

Usage:
    python3 .claude/skills/skill-design/cluster-skills.py
    python3 .claude/skills/skill-design/cluster-skills.py --target 10
    python3 .claude/skills/skill-design/cluster-skills.py --json
    python3 .claude/skills/skill-design/cluster-skills.py --apply
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parent.parent.parent  # .claude/
BANK_DIR = CLAUDE_DIR / "skill-bank"
SKILLS_DIR = CLAUDE_DIR / "skills"

# Auto-detect: prefer skill-bank/ if it exists
def _get_source_dir() -> Path:
    return BANK_DIR if BANK_DIR.is_dir() else SKILLS_DIR


# --- Stop words: English common + skill-description boilerplate ---
STOP_WORDS: set[str] = {
    # English
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "must",
    "it", "its", "this", "that", "these", "those", "not", "no", "nor",
    "if", "then", "else", "when", "where", "how", "what", "which", "who",
    "whom", "why", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "than", "too", "very", "just", "also",
    "about", "above", "after", "again", "any", "as", "because", "before",
    "between", "during", "into", "out", "over", "own", "same", "so",
    "through", "under", "until", "up", "while",
    # Skill-description boilerplate
    "use", "using", "used", "apply", "applying", "ensures", "ensure",
    "based", "across", "via", "e", "g", "eg", "etc", "i",
}


# ──────────────────────────────────────────────────────────────────────
# 1. Parse frontmatter
# ──────────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract name and description from YAML frontmatter."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    block = match.group(1)
    result: dict[str, str] = {}
    for field in ("name", "description"):
        m = re.search(rf"^{field}:\s*(.+)$", block, re.MULTILINE)
        if m:
            result[field] = m.group(1).strip()
    return result


def load_skills(source_dir: Path) -> list[dict[str, str]]:
    """Load all leaf skills from a flat skill directory."""
    skills: list[dict[str, str]] = []
    for skill_dir in sorted(source_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        # Skip if this dir has subdirs with SKILL.md (it's a category, not a leaf)
        has_children = any(
            (child / "SKILL.md").is_file()
            for child in skill_dir.iterdir()
            if child.is_dir()
        )
        if has_children:
            continue

        fm = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        if fm.get("name") and fm.get("description"):
            skills.append({
                "name": fm["name"],
                "dir": skill_dir.name,
                "path": str(skill_file),
                "description": fm["description"],
            })
        else:
            print(f"  WARN: {skill_dir.name} — missing name/description, skipping",
                  file=sys.stderr)
    return skills


# ──────────────────────────────────────────────────────────────────────
# 2. Tokenize
# ──────────────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, remove stop words and short tokens."""
    tokens = re.findall(r"[a-z][a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


# ──────────────────────────────────────────────────────────────────────
# 3. TF-IDF
# ──────────────────────────────────────────────────────────────────────

def build_tfidf(docs: list[list[str]]) -> tuple[list[dict[str, float]], list[str]]:
    """Compute TF-IDF vectors for a list of tokenized documents.

    Returns (vectors, vocabulary) where each vector is {term: tfidf_score}.
    """
    n = len(docs)

    # Document frequency: how many docs contain each term
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))

    # Build vocabulary (sorted for determinism)
    vocab = sorted(df.keys())

    # IDF: log(N / df(t)) with smoothing
    idf: dict[str, float] = {}
    for term in vocab:
        idf[term] = math.log((n + 1) / (df[term] + 1)) + 1  # sklearn-style smooth

    # TF-IDF per document
    vectors: list[dict[str, float]] = []
    for doc in docs:
        tf = Counter(doc)
        doc_len = len(doc) if doc else 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            vec[term] = (count / doc_len) * idf.get(term, 0)

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vec = {t: v / norm for t, v in vec.items()}
        vectors.append(vec)

    return vectors, vocab


# ──────────────────────────────────────────────────────────────────────
# 4. Cosine similarity
# ──────────────────────────────────────────────────────────────────────

def cosine_sim(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse L2-normalized vectors."""
    shared = set(a.keys()) & set(b.keys())
    return sum(a[t] * b[t] for t in shared)


def build_distance_matrix(vectors: list[dict[str, float]]) -> list[list[float]]:
    """Build symmetric distance matrix (1 - cosine_similarity)."""
    n = len(vectors)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = 1.0 - cosine_sim(vectors[i], vectors[j])
            dist[i][j] = d
            dist[j][i] = d
    return dist


# ──────────────────────────────────────────────────────────────────────
# 5. Agglomerative clustering (average linkage)
# ──────────────────────────────────────────────────────────────────────

def agglomerative_cluster(
    dist: list[list[float]],
    n: int,
    *,
    target_clusters: int | None = None,
    threshold: float | None = None,
) -> list[list[int]]:
    """Average-linkage agglomerative clustering.

    Returns list of clusters (each cluster is a list of original indices).
    Stops when target_clusters is reached OR merge distance exceeds threshold.
    """
    clusters: dict[int, list[int]] = {i: [i] for i in range(n)}
    active: set[int] = set(range(n))

    cdist: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            cdist[(i, j)] = dist[i][j]

    while len(active) > 1:
        if target_clusters and len(active) <= target_clusters:
            break

        best_pair: tuple[int, int] | None = None
        best_dist = float("inf")
        for i in sorted(active):
            for j in sorted(active):
                if j <= i:
                    continue
                key = (min(i, j), max(i, j))
                d = cdist.get(key, float("inf"))
                if d < best_dist:
                    best_dist = d
                    best_pair = key

        if best_pair is None:
            break

        if threshold is not None and best_dist > threshold:
            break

        ci, cj = best_pair
        new_members = clusters[ci] + clusters[cj]
        new_id = ci

        for k in sorted(active):
            if k == ci or k == cj:
                continue
            key_ik = (min(new_id, k), max(new_id, k))
            key_ci_k = (min(ci, k), max(ci, k))
            key_cj_k = (min(cj, k), max(cj, k))

            d_ci_k = cdist.get(key_ci_k, float("inf"))
            d_cj_k = cdist.get(key_cj_k, float("inf"))

            size_ci = len(clusters[ci])
            size_cj = len(clusters[cj])
            new_dist = (d_ci_k * size_ci + d_cj_k * size_cj) / (size_ci + size_cj)
            cdist[key_ik] = new_dist

        clusters[new_id] = new_members
        del clusters[cj]
        active.discard(cj)

        to_remove = [k for k in cdist if cj in k]
        for k in to_remove:
            del cdist[k]

    return [members for members in clusters.values()]


# ──────────────────────────────────────────────────────────────────────
# 6. Cluster labeling
# ──────────────────────────────────────────────────────────────────────

def label_cluster(
    member_indices: list[int],
    vectors: list[dict[str, float]],
) -> str:
    """Generate a category label from the cluster's most distinctive terms."""
    term_scores: dict[str, float] = {}
    for idx in member_indices:
        for term, score in vectors[idx].items():
            term_scores[term] = term_scores.get(term, 0.0) + score

    size = len(member_indices)
    for term in term_scores:
        term_scores[term] /= size

    ranked = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)

    generic = {"patterns", "code", "workflow", "design", "implementation",
               "writing", "tools", "methodology", "tasks", "approach"}
    candidates = [
        (term, score) for term, score in ranked[:10]
        if term not in generic
    ]

    if not candidates:
        candidates = ranked[:3]

    top = [t for t, _ in candidates[:2]]
    return "-".join(top) if top else "misc"


# ──────────────────────────────────────────────────────────────────────
# 7. Auto-detect best threshold
# ──────────────────────────────────────────────────────────────────────

def find_best_threshold(
    dist: list[list[float]],
    n: int,
    min_clusters: int = 7,
    max_clusters: int = 12,
) -> tuple[float, int]:
    """Binary search for a threshold that yields clusters in target range."""
    lo, hi = 0.0, 2.0
    best_threshold = 1.0
    best_count = n

    for _ in range(50):
        mid = (lo + hi) / 2
        clusters = agglomerative_cluster(dist, n, threshold=mid)
        count = len(clusters)

        if min_clusters <= count <= max_clusters:
            return mid, count

        if count > max_clusters:
            lo = mid
            if count < best_count or (count == best_count and mid < best_threshold):
                best_threshold = mid
                best_count = count
        else:
            hi = mid
            if abs(count - max_clusters) < abs(best_count - max_clusters):
                best_threshold = mid
                best_count = count

    return best_threshold, best_count


# ──────────────────────────────────────────────────────────────────────
# 8. Apply categories to frontmatter
# ──────────────────────────────────────────────────────────────────────

def write_category_to_frontmatter(skill_path: str, category: str) -> bool:
    """Insert or replace `category: {value}` in a skill's YAML frontmatter.

    Inserts after `description:` if category doesn't exist.
    Returns True if the file was modified.
    """
    path = Path(skill_path)
    text = path.read_text(encoding="utf-8")

    fm_match = re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.DOTALL)
    if not fm_match:
        return False

    prefix = fm_match.group(1)   # "---\n"
    block = fm_match.group(2)    # frontmatter body
    suffix = fm_match.group(3)   # "\n---"
    rest = text[fm_match.end():]  # everything after frontmatter

    # Check if category already exists
    cat_pattern = re.compile(r"^category:\s*.*$", re.MULTILINE)
    if cat_pattern.search(block):
        new_block = cat_pattern.sub(f"category: {category}", block)
    else:
        # Insert after description line (or after name if no description)
        desc_match = re.search(r"^description:\s*.+$", block, re.MULTILINE)
        if desc_match:
            insert_pos = desc_match.end()
        else:
            name_match = re.search(r"^name:\s*.+$", block, re.MULTILINE)
            insert_pos = name_match.end() if name_match else len(block)
        new_block = block[:insert_pos] + f"\ncategory: {category}" + block[insert_pos:]

    if new_block == block:
        return False

    path.write_text(prefix + new_block + suffix + rest, encoding="utf-8")
    return True


# ──────────────────────────────────────────────────────────────────────
# 9. Main
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propose skill categories via TF-IDF + agglomerative clustering."
    )
    parser.add_argument(
        "--target", type=int, default=None,
        help="Exact number of clusters (overrides auto-detection)",
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="Distance threshold for cutting dendrogram (0.0-2.0)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON instead of formatted table",
    )
    parser.add_argument(
        "--min-clusters", type=int, default=7,
        help="Minimum clusters for auto-detection (default: 7)",
    )
    parser.add_argument(
        "--max-clusters", type=int, default=12,
        help="Maximum clusters for auto-detection (default: 12)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write category field into each skill's YAML frontmatter",
    )
    parser.add_argument(
        "--source", type=Path, default=None,
        help="Skill source directory (default: auto-detect skill-bank/ or skills/)",
    )
    args = parser.parse_args()

    source_dir: Path = args.source if args.source else _get_source_dir()

    # Load skills
    print(f"Loading skills from {source_dir}...", file=sys.stderr)
    skills = load_skills(source_dir)
    if not skills:
        print("No skills found.", file=sys.stderr)
        return
    print(f"Found {len(skills)} skills.", file=sys.stderr)

    # Tokenize: combine name (split on hyphens) + description
    docs: list[list[str]] = []
    for s in skills:
        name_tokens = s["name"].replace("-", " ").split()
        desc_tokens = tokenize(s["description"])
        docs.append(tokenize(" ".join(name_tokens)) + desc_tokens)

    # TF-IDF
    vectors, vocab = build_tfidf(docs)
    print(f"Vocabulary: {len(vocab)} terms.", file=sys.stderr)

    # Distance matrix
    dist = build_distance_matrix(vectors)

    # Cluster
    n = len(skills)
    if args.target:
        clusters = agglomerative_cluster(dist, n, target_clusters=args.target)
        print(f"Clustered into {len(clusters)} groups (target={args.target}).",
              file=sys.stderr)
    elif args.threshold is not None:
        clusters = agglomerative_cluster(dist, n, threshold=args.threshold)
        print(f"Clustered into {len(clusters)} groups (threshold={args.threshold:.3f}).",
              file=sys.stderr)
    else:
        threshold, _ = find_best_threshold(
            dist, n, args.min_clusters, args.max_clusters
        )
        clusters = agglomerative_cluster(dist, n, threshold=threshold)
        print(f"Auto-detected threshold={threshold:.4f} → {len(clusters)} clusters.",
              file=sys.stderr)

    # Sort clusters by size descending, then by first member name
    clusters.sort(key=lambda c: (-len(c), skills[c[0]]["name"]))

    # Build output
    categories: list[tuple[str, list[dict[str, str]]]] = []
    for members in clusters:
        label = label_cluster(members, vectors)
        member_skills = sorted(
            [skills[i] for i in members],
            key=lambda s: s["name"],
        )
        categories.append((label, member_skills))

    # Apply mode: write category to frontmatter
    if args.apply:
        modified = 0
        for label, member_skills in categories:
            for skill in member_skills:
                if write_category_to_frontmatter(skill["path"], label):
                    modified += 1
                    print(f"  SET {skill['name']} → category: {label}",
                          file=sys.stderr)
        print(f"\nApplied categories to {modified} skills.", file=sys.stderr)
        return

    # Output
    if args.json_output:
        json_out = [
            {
                "category": label,
                "count": len(member_skills),
                "skills": [s["name"] for s in member_skills],
            }
            for label, member_skills in categories
        ]
        print(json.dumps(json_out, indent=2))
    else:
        print()
        for i, (cat, member_skills) in enumerate(categories, 1):
            print(f"{'─'*60}")
            print(f"  Category {i}: {cat}  ({len(member_skills)} skills)")
            print(f"{'─'*60}")
            for skill in member_skills:
                print(f"    - {skill['name']}")
            print()

        total = sum(len(ms) for _, ms in categories)
        print(f"Total: {total} skills in {len(categories)} categories")


if __name__ == "__main__":
    main()
