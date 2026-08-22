from __future__ import annotations

from dataclasses import dataclass

from huggingface_hub import scan_cache_dir


@dataclass(frozen=True)
class CachedRepo:
    repo_id: str
    size_bytes: int
    revision_hashes: tuple[str, ...]
    last_modified: float
    local_path: str


def scan_downloaded() -> dict[str, CachedRepo]:
    """Map Hugging Face repo id -> cache info for every model in the local cache."""
    try:
        cache_info = scan_cache_dir()
    except Exception:
        return {}

    repos: dict[str, CachedRepo] = {}
    for repo in cache_info.repos:
        if repo.repo_type != "model":
            continue
        repos[repo.repo_id] = CachedRepo(
            repo_id=repo.repo_id,
            size_bytes=repo.size_on_disk,
            revision_hashes=tuple(rev.commit_hash for rev in repo.revisions),
            last_modified=repo.last_modified,
            local_path=str(repo.repo_path),
        )
    return repos


def delete_repo(repo_id: str) -> int:
    """Delete every cached revision of repo_id. Returns bytes freed."""
    cache_info = scan_cache_dir()
    matches = [repo for repo in cache_info.repos if repo.repo_id == repo_id]
    if not matches:
        raise KeyError(f"{repo_id!r} is not in the local Hugging Face cache")

    freed = sum(repo.size_on_disk for repo in matches)
    hashes = [rev.commit_hash for repo in matches for rev in repo.revisions]
    cache_info.delete_revisions(*hashes).execute()
    return freed
