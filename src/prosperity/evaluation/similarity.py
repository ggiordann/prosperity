from __future__ import annotations

import ast
import io
import tokenize
from typing import Iterable

from prosperity.dsl.normalization import normalized_spec_json
from prosperity.dsl.schema import StrategySpec


def _token_stream(code: str) -> list[str]:
    stream = io.StringIO(code)
    tokens = []
    for token in tokenize.generate_tokens(stream.readline):
        if token.type in {tokenize.NAME, tokenize.NUMBER, tokenize.OP, tokenize.STRING}:
            tokens.append(token.string)
    return tokens


def _shingles(items: Iterable[str], width: int = 5) -> set[tuple[str, ...]]:
    items = list(items)
    if len(items) < width:
        return {tuple(items)} if items else set()
    return {tuple(items[index : index + width]) for index in range(len(items) - width + 1)}


def jaccard_similarity(left: set, right: set) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def code_similarity(left_code: str, right_code: str) -> dict:
    token_score = jaccard_similarity(_shingles(_token_stream(left_code)), _shingles(_token_stream(right_code)))
    ast_score = ast_similarity(left_code, right_code)
    return {
        "token_jaccard": token_score,
        "ast_similarity": ast_score,
        "combined": 0.5 * token_score + 0.5 * ast_score,
    }


def ast_similarity(left_code: str, right_code: str) -> float:
    try:
        left_nodes = [type(node).__name__ for node in ast.walk(ast.parse(left_code))]
        right_nodes = [type(node).__name__ for node in ast.walk(ast.parse(right_code))]
    except SyntaxError:
        return 0.0
    return jaccard_similarity(_shingles(left_nodes, width=3), _shingles(right_nodes, width=3))


def spec_similarity(left: StrategySpec, right: StrategySpec) -> float:
    return jaccard_similarity(
        _shingles(normalized_spec_json(left), width=16),
        _shingles(normalized_spec_json(right), width=16),
    )
