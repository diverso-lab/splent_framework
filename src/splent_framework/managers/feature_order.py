"""
FeatureLoadOrderResolver — topological sort of features based on UVL constraints.

Directly applies the ACTREQ activation principle from:
  "We're Not Gonna Break It! Consistency-Preserving Operators for Efficient
   Product Line Configuration" — Horcas et al., IEEE TSE 2023

The paper observes that activating feature A, when A requires B, mandates
that B must already be active. We apply the same logic to load order:
if the UVL declares 'A => B' (A requires B), then B must be loaded before A.

Algorithm
---------
1. Parse the UVL file to extract:
   - A short-name → package-name mapping from feature attribute blocks
     (e.g.  auth {package 'splent_feature_auth'})
   - 'requires' constraints (A => B)

2. Build a dependency graph over package names:
   for each (A requires B) where both are in the active feature set:
       add directed edge B → A  (B must come before A)
       increment in_degree[A]

3. Run a stable Kahn topological sort:
   - Use a min-heap keyed by original pyproject.toml index so that
     independent features always preserve their declared order.
   - If the sorted result is shorter than the input, a cycle exists →
     raise FeatureError naming the involved features.

4. Return the original pyproject entries reordered by the sorted indices.

Falls back to the original pyproject.toml order (with a debug log) when:
  - No UVL file path is given
  - The UVL file does not exist on disk
  - The UVL defines no constraints that apply to the active feature set
"""

import heapq
import logging
import os
import re
from pathlib import Path

from splent_framework.managers.feature_loader import FeatureEntryParser, FeatureError

logger = logging.getLogger(__name__)


class FeatureLoadOrderResolver:
    """
    Resolve the correct load order for features declared in pyproject.toml.

    If feature A declares 'A => B' in the UVL (A requires B), B is guaranteed
    to be loaded before A.  Independent features preserve their original
    pyproject.toml order (stable sort).

    Usage::

        resolver = FeatureLoadOrderResolver()
        ordered = resolver.resolve(features_raw, uvl_path)
    """

    def __init__(self, parser: FeatureEntryParser | None = None) -> None:
        self._parser = parser or FeatureEntryParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, features_raw: list[str], uvl_path: str | None) -> list[str]:
        """Return *features_raw* reordered to respect UVL dependency constraints.

        Args:
            features_raw: Raw feature entries from pyproject.toml.
            uvl_path:     Absolute path to the product's .uvl file, or None.

        Returns:
            Reordered list. Independent features keep their original order.

        Raises:
            FeatureError: If a circular dependency is detected.
        """
        if not features_raw:
            return features_raw

        if not uvl_path or not os.path.isfile(uvl_path):
            if uvl_path:
                logger.debug(
                    "UVL not found at %s — preserving pyproject.toml load order",
                    uvl_path,
                )
            return features_raw

        uvl_text = Path(uvl_path).read_text(encoding="utf-8", errors="replace")
        package_map = self._parse_package_map(uvl_text)
        constraints = self._parse_constraints(uvl_text)

        if not constraints:
            return features_raw

        ordered = self._topological_sort(features_raw, package_map, constraints)
        if ordered != features_raw:
            reordered = [self._parser.parse(e).name for e in ordered]
            logger.info("Feature load order resolved by UVL constraints: %s", reordered)
        return ordered

    # ------------------------------------------------------------------
    # UVL parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_package_map(uvl_text: str) -> dict[str, str]:
        """Parse ``{short_name → package_name}`` from UVL feature attribute blocks.

        Handles lines such as::

            auth {org 'splent-io', package 'splent_feature_auth', version 'v1.0.0'}
        """
        mapping: dict[str, str] = {}
        for line in uvl_text.splitlines():
            stripped = line.strip()
            m_name = re.match(r"^(\w+)\s*\{", stripped)
            m_pkg = re.search(r"package\s+['\"]([^'\"]+)['\"]", stripped)
            if m_name and m_pkg:
                mapping[m_name.group(1)] = m_pkg.group(1)
        return mapping

    @staticmethod
    def _parse_constraints(uvl_text: str) -> list[tuple[str, str]]:
        """Parse implication constraints (``A => B``) from UVL text.

        Returns a list of ``(requirer_short_name, required_short_name)`` tuples.
        Only simple binary implications are supported (matching SPLENT's UVL dialect).
        """
        pairs: list[tuple[str, str]] = []
        for line in uvl_text.splitlines():
            line = line.strip().replace("=&gt;", "=>")
            if not line or line.startswith("//"):
                continue
            m = re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*([A-Za-z_][A-Za-z0-9_]*)\s*$",
                line,
            )
            if m:
                pairs.append((m.group(1), m.group(2)))
        return pairs

    # ------------------------------------------------------------------
    # Topological sort — Kahn's algorithm (stable)
    # ------------------------------------------------------------------

    def _topological_sort(
        self,
        features_raw: list[str],
        package_map: dict[str, str],  # {short_name → package_name}
        constraints: list[tuple[str, str]],  # [(requirer_short, required_short)]
    ) -> list[str]:
        """Stable Kahn topological sort over *features_raw*.

        Features with no mutual dependency preserve their original order.
        Raises FeatureError if a circular dependency is detected.
        """
        # Resolve each entry to its package name via FeatureEntryParser.
        # Pair: (original_index, raw_entry, package_name)
        parsed: list[tuple[int, str, str]] = [
            (i, entry, self._parser.parse(entry).name)
            for i, entry in enumerate(features_raw)
        ]
        pkg_to_index: dict[str, int] = {pkg: i for i, _, pkg in parsed}

        # Build reverse lookup: package_name → UVL short name (for error messages)
        pkg_to_short: dict[str, str] = {v: k for k, v in package_map.items()}

        # Initialise graph and in-degree counters.
        in_degree: dict[str, int] = {pkg: 0 for pkg in pkg_to_index}
        # graph[B] = [A, ...] means "A depends on B → B must load before A"
        graph: dict[str, list[str]] = {pkg: [] for pkg in pkg_to_index}

        active_constraints = 0
        for requirer_short, required_short in constraints:
            requirer_pkg = package_map.get(requirer_short)
            required_pkg = package_map.get(required_short)

            # Skip constraints that reference features not in the active set.
            if requirer_pkg not in pkg_to_index or required_pkg not in pkg_to_index:
                continue

            graph[required_pkg].append(requirer_pkg)
            in_degree[requirer_pkg] += 1
            active_constraints += 1
            logger.debug(
                "Ordering constraint: %s must load before %s",
                required_pkg,
                requirer_pkg,
            )

        if active_constraints == 0:
            return features_raw  # No applicable constraints — keep original order.

        # Min-heap keyed by original pyproject index → stable ordering.
        heap: list[tuple[int, str]] = [
            (pkg_to_index[pkg], pkg) for pkg, deg in in_degree.items() if deg == 0
        ]
        heapq.heapify(heap)

        sorted_indices: list[int] = []

        while heap:
            _, pkg = heapq.heappop(heap)
            sorted_indices.append(pkg_to_index[pkg])
            for dependent in graph[pkg]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    heapq.heappush(heap, (pkg_to_index[dependent], dependent))

        if len(sorted_indices) != len(features_raw):
            # Not all nodes were processed → cycle exists.
            cycle_pkgs = [pkg for pkg, deg in in_degree.items() if deg > 0]
            cycle_names = [pkg_to_short.get(p, p) for p in cycle_pkgs]
            raise FeatureError(
                f"Circular dependency detected among features: {cycle_names}. "
                f"Review the 'constraints' section in your .uvl file."
            )

        return [features_raw[i] for i in sorted_indices]
