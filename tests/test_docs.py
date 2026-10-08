"""Documentation must not drift from the code."""
from pathlib import Path

from picore.reasoning.mistakes import RULES

DOCS = Path(__file__).resolve().parent.parent / "docs"


def test_every_mistake_rule_is_documented():
    catalogue = (DOCS / "MISTAKES.md").read_text(encoding="utf-8")
    missing = [r.id for r in RULES if f"`{r.id}`" not in catalogue]
    assert not missing, f"add these rules to docs/MISTAKES.md: {missing}"


def test_grammar_doc_mentions_every_conventions_example():
    grammar = (DOCS / "GRAMMAR.md").read_text(encoding="utf-8")
    for example in ("-2^2", "2^3^2", "1/2x", "sin x^2", "sin^2 x", "√x^2", "d/dx x^2 + 1"):
        assert f"`{example}`" in grammar, example
