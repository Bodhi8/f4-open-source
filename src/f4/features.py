"""Small public graph reference functions; no production detector thresholds."""

from collections import defaultdict
from collections.abc import Iterable


def basic_graph_features(edges: Iterable[tuple[str, str]]) -> dict[str, dict[str, int]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        if a != b:
            adjacency[a].add(b)
            adjacency[b].add(a)
    result = {}
    remaining = set(adjacency)
    while remaining:
        stack = [min(remaining)]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node not in component:
                component.add(node)
                stack.extend(adjacency[node] - component)
        remaining -= component
        for node in component:
            result[node] = {"degree": len(adjacency[node]), "component_size": len(component)}
    return result
