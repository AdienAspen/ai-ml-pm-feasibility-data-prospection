"""Public adaptation of structural profile inheritance and code scoping.

The profile-to-type-to-group-to-code chain is evaluated as separate joins.
No original hierarchy, profile, group, or code values are distributed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Node:
    node_id: str
    parent_id: str | None
    profile_id: str | None


def effective_profile(
    node_id: str,
    nodes: Mapping[str, Node],
    valid_profiles: set[str],
) -> tuple[str | None, int]:
    """Walk to the nearest valid ancestor, returning profile and depth walked."""
    seen: set[str] = set()
    current = node_id
    depth = 0
    while current:
        if current in seen:
            raise ValueError("Cycle in functional-location hierarchy")
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            return None, depth
        if node.profile_id in valid_profiles:
            return node.profile_id, depth
        current = node.parent_id
        depth += 1
    return None, depth


def enabled_codes(
    profile_id: str,
    catalog_type: str,
    profile_groups: Iterable[tuple[str, str, str]],
    group_codes: Iterable[tuple[str, str, str]],
) -> set[tuple[str, str]]:
    """Expand an allowed group into codes; groups and codes are different units."""
    groups = {
        group
        for profile, kind, group in profile_groups
        if profile == profile_id and kind == catalog_type
    }
    return {
        (group, code)
        for kind, group, code in group_codes
        if kind == catalog_type and group in groups
    }


def consensus_profile(candidate_profiles: Iterable[str | None]) -> str | None:
    """A tied node can still resolve a profile when all candidates share it."""
    values = list(candidate_profiles)
    if not values or any(value is None for value in values):
        return None
    unique = set(values)
    return next(iter(unique)) if len(unique) == 1 else None
