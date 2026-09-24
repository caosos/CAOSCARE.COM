"""Weighted phoneme alignment (stress-free base phonemes).

- global_distance: whole-sequence edit distance (word/phrase sounds like the
  candidate as a whole).
- best_substring: cheapest alignment of a short sequence against ANY
  contiguous span of a longer one (free leading/trailing material in the
  long sequence). Used both ways: the candidate hidden inside a phrase
  ("that area" contains "area"), and a common word hidden inside the
  candidate.

Distances are normalised by the length of the sequence being searched for,
so 0.0 = exact, ~0.1 = one close vowel swap in a 4-phoneme word.
"""
from ..phonetics.features import indel_cost, sub_cost


def global_distance(a, b):
    """Weighted Levenshtein between phoneme tuples a and b (raw cost)."""
    prev = [0.0]
    for y in b:
        prev.append(prev[-1] + indel_cost(y))
    for x in a:
        cur = [prev[0] + indel_cost(x)]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + indel_cost(x),
                           cur[j - 1] + indel_cost(y),
                           prev[j - 1] + sub_cost(x, y)))
        prev = cur
    return prev[-1]


def normalized_global(a, b):
    return global_distance(a, b) / max(len(a), len(b), 1)


def best_substring(short, long):
    """Cheapest alignment of `short` to a span of `long`.

    Returns (normalised_distance, start, end) with long[start:end] the span.
    Leading/trailing parts of `long` are free.
    """
    n = len(long)
    # prev[j] = (cost, start) aligning short[:i] ending at long[:j]
    prev = [(0.0, j) for j in range(n + 1)]
    for x in short:
        cur = [(prev[0][0] + indel_cost(x), 0)]
        for j, y in enumerate(long, 1):
            cur.append(min((prev[j][0] + indel_cost(x), prev[j][1]),
                           (cur[j - 1][0] + indel_cost(y), cur[j - 1][1]),
                           (prev[j - 1][0] + sub_cost(x, y), prev[j - 1][1])))
        prev = cur
    end = min(range(n + 1), key=lambda j: (prev[j][0], j))
    cost, start = prev[end]
    return cost / max(len(short), 1), start, end
