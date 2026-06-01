"""Aspect hashing & node identity.

Each node hashes its facets independently (``raw``, ``frontmatter``, ``body``,
``content_html``, ...). Hashing is ``blake2b`` over newline-normalized bytes so a
``\\r\\n`` vs ``\\n`` difference never spuriously invalidates. Everything here is
deterministic and stdlib-only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pyssg.core.node import Node
from pyssg.core.types import Aspect, Digest, NodeId

# 16-byte digests keep per-aspect hash maps compact for large wikis.
_DIGEST_SIZE = 16


def canonical_bytes(value: object) -> bytes:
    """Deterministic byte encoding of a value for hashing.

    ``bytes``/``str`` pass through (str newline-normalized); everything else goes
    through canonical JSON (sorted keys, compact) so dict/list ordering can never
    change the digest.
    """
    if isinstance(value, bytes):
        return value.replace(b"\r\n", b"\n")
    if isinstance(value, str):
        return value.replace("\r\n", "\n").encode("utf-8")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False
    ).encode("utf-8")


def compute_raw_hash(data: bytes) -> Digest:
    """Hash raw file bytes with newline normalization."""
    return hashlib.blake2b(data.replace(b"\r\n", b"\n"), digest_size=_DIGEST_SIZE).hexdigest()


def digest(*parts: object) -> Digest:
    """Combine several values into one digest (used for composite cache keys)."""
    h = hashlib.blake2b(digest_size=_DIGEST_SIZE)
    for part in parts:
        h.update(canonical_bytes(part))
        h.update(b"\x00")  # unambiguous separator
    return h.hexdigest()


def hash_aspect(node: Node, aspect: Aspect, value: object) -> Digest:
    """Compute, store and return the digest of one aspect of ``node``."""
    node.hashes[aspect] = digest(value)
    return node.hashes[aspect]


def resolve_identity(
    path: str,
    fm: Mapping[str, object],
    raw_hash: Digest,
    recently_deleted: dict[Digest, NodeId],
) -> NodeId:
    """Resolve the stable logical ``NodeId`` for a file.

    Order: frontmatter ``id`` -> move-detect (raw hash of a just-deleted node) ->
    ``slug`` -> path fallback. This is what keeps backlinks intact across renames.
    """
    fid = fm.get("id")
    if fid:
        return f"id:{fid}"
    if raw_hash in recently_deleted:
        return recently_deleted[raw_hash]  # move detected
    slug = fm.get("slug")
    if slug:
        return f"slug:{slug}"
    return f"path:{path}"
