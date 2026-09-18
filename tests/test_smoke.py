"""Baseline smoke test: the core package imports without the GUI."""


def test_core_imports():
    from saldoboek.core import DatabaseManager, TransactionImporter  # noqa: F401
    from saldoboek.core.parsers import KnabParser, RaboParser, SNSParser  # noqa: F401
