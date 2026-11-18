from __future__ import annotations

import math
import re
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = {".md", ".py", ".txt", ".toml", ".json", ".yaml", ".yml"}
IGNORED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".agent-data", ".memory", ".tasks", ".workflows", ".background", "evals"}
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class Chunk:
    path: str
    title: str
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float
    sparse_score: float
    dense_score: float


class ProjectKnowledgeIndex:
    """Small local hybrid index: BM25-style lexical scoring plus hashed token vectors."""

    def __init__(self, workspace: Path, *, max_file_bytes: int = 1_000_000, max_files: int = 5000):
        self.workspace = workspace.resolve()
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.chunks: list[Chunk] = []
        self._terms: list[list[str]] = []
        self._doc_freq: Counter[str] = Counter()
        self._avg_len = 0.0
        self._vectors: list[dict[str, float]] = []
        self.file_manifest: dict[str, str] = {}

    def build(self) -> int:
        chunks: list[Chunk] = []
        paths = []
        manifest: dict[str, str] = {}
        for path in sorted(self.workspace.rglob("*")):
            relative = path.relative_to(self.workspace)
            if any(part in IGNORED_PARTS or part.startswith(".pytest-run") or part.startswith(".workflow-debug") for part in relative.parts):
                continue
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES and path.stat().st_size <= self.max_file_bytes:
                paths.append(path)
                manifest[path.relative_to(self.workspace).as_posix()] = _file_digest(path)
                if len(paths) >= self.max_files:
                    break
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks.extend(_chunk_document(path.relative_to(self.workspace).as_posix(), text))
        self.chunks = chunks
        self._terms = [_tokens(chunk.text + " " + chunk.title + " " + chunk.path) + _identifier_tokens(chunk.text + " " + chunk.path) for chunk in chunks]
        self._doc_freq = Counter(term for terms in self._terms for term in set(terms))
        self._avg_len = sum(map(len, self._terms)) / max(1, len(self._terms))
        self._vectors = [_hashed_vector(terms) for terms in self._terms]
        self.file_manifest = manifest
        return len(chunks)

    def manifest_json(self) -> str:
        """Stable manifest for detecting incremental index changes."""
        return json.dumps(self.file_manifest, ensure_ascii=False, sort_keys=True)

    def search(self, query: str, *, top_k: int = 5, path_prefix: str | None = None) -> list[SearchResult]:
        query_terms = _tokens(query)
        if not query_terms or not self.chunks:
            return []
        query_vector = _hashed_vector(query_terms)
        sparse = [self._bm25(query_terms, terms) for terms in self._terms]
        dense = [_cosine(query_vector, vector) for vector in self._vectors]
        max_sparse = max(sparse, default=0.0) or 1.0
        candidates = []
        for index, chunk in enumerate(self.chunks):
            if path_prefix and not chunk.path.lower().startswith(path_prefix.replace("\\", "/").lower().rstrip("/") + "/") and chunk.path.lower() != path_prefix.replace("\\", "/").lower():
                continue
            sparse_norm = sparse[index] / max_sparse
            dense_score = dense[index]
            # Lexical precision is more useful for code symbols and identifiers; hashed similarity is a weak recall signal.
            exact_path_bonus = 0.35 if chunk.path.lower() in query.lower().replace("\\", "/") else 0.0
            identifier_bonus = 0.0
            for term in set(query_terms):
                if term in chunk.path.lower().replace("\\", "/") or term in chunk.title.lower():
                    identifier_bonus += 0.04
            score = 0.85 * sparse_norm + 0.15 * dense_score + exact_path_bonus + min(identifier_bonus, 0.2)
            if score > 0:
                candidates.append(SearchResult(chunk, round(score, 6), round(sparse_norm, 6), round(dense_score, 6)))
        candidates.sort(key=lambda item: (-item.score, item.chunk.path, item.chunk.start_line))
        unique: dict[str, SearchResult] = {}
        for item in candidates:
            unique.setdefault(item.chunk.path, item)
        return list(unique.values())[:max(1, min(int(top_k), 20))]

    def format_results(self, query: str, *, top_k: int = 5, path_prefix: str | None = None) -> str:
        matches = self.search(query, top_k=top_k, path_prefix=path_prefix)
        if not matches:
            return "No relevant project knowledge found."
        return "\n\n".join(
            f"[{item.chunk.path}:{item.chunk.start_line}-{item.chunk.end_line}] {item.chunk.title} (score={item.score:.3f})\n"
            f"{item.chunk.text}" for item in matches
        )

    def _bm25(self, query_terms: list[str], document_terms: list[str]) -> float:
        frequencies = Counter(document_terms)
        score = 0.0
        count = max(1, len(self.chunks))
        for term in query_terms:
            tf = frequencies[term]
            if not tf:
                continue
            df = self._doc_freq[term]
            inverse = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = tf + 1.5 * (1 - 0.75 + 0.75 * len(document_terms) / max(1.0, self._avg_len))
            score += inverse * (tf * 2.5 / denominator)
        return score


def _tokens(text: str) -> list[str]:
    tokens = []
    for match in TOKEN_RE.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            # Character bigrams give a dependency-free baseline for Chinese queries.
            tokens.extend(match[index:index + 2] for index in range(max(1, len(match) - 1)))
            if len(match) == 1:
                tokens.append(match)
        else:
            tokens.append(match)
    return tokens


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identifier_tokens(text: str) -> list[str]:
    """Expose path and code identifiers as both whole names and searchable components."""
    result: list[str] = []
    for identifier in re.findall(r"[A-Za-z_][A-Za-z0-9_./:-]*", text):
        normalized = identifier.lower()
        result.append(normalized)
        result.extend(part for part in re.split(r"[_./:-]+", normalized) if len(part) > 1)
    return result


def _hashed_vector(terms: list[str], dimensions: int = 2048) -> dict[str, float]:
    # Signed feature hashing is deterministic and needs no external embedding service.
    vector: defaultdict[str, float] = defaultdict(float)
    for term in terms:
        value = int.from_bytes(hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest(), "big")
        index = value % dimensions
        vector[str(index)] += 1.0 if (value >> 8) & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {key: value / norm for key, value in vector.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())


def _chunk_document(path: str, text: str, max_lines: int = 45) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    chunks: list[Chunk] = []
    start = 0
    title = Path(path).name
    buffer: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if path.endswith(".md") and stripped.startswith("#"):
            if buffer:
                chunks.append(Chunk(path, title, start + 1, index, "\n".join(buffer).strip()))
                buffer = []
            title = stripped.lstrip("# ") or Path(path).name
            start = index
        buffer.append(line)
        if len(buffer) >= max_lines:
            chunks.append(Chunk(path, title, start + 1, index + 1, "\n".join(buffer).strip()))
            buffer = []
            start = index + 1
    if buffer:
        chunks.append(Chunk(path, title, start + 1, len(lines), "\n".join(buffer).strip()))
    return [chunk for chunk in chunks if chunk.text]

