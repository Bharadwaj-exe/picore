from picore.storage import History


def test_save_fetch_and_dedupe(tmp_path):
    h = History(tmp_path / "h.db")
    h.save("2+2", [("Input", "2+2"), ("Result", "4")])
    h.save("x^2", [("Input", "x^2")])
    h.save("2+2", [("Input", "2+2"), ("Result", "4")])   # re-run moves to top, no duplicate

    items = h.fetch()
    assert [it.expression for it in items] == ["2+2", "x^2"]
    assert items[0].results == [("Input", "2+2"), ("Result", "4")]
    assert h.recent_expressions() == ["2+2", "x^2"]


def test_limit_counts_queries_not_result_rows(tmp_path):
    h = History(tmp_path / "h.db")
    for i in range(5):
        h.save(f"q{i}", [("a", "1"), ("b", "2"), ("c", "3")])
    items = h.fetch(limit=2)
    assert len(items) == 2 and all(len(it.results) == 3 for it in items)


def test_clear(tmp_path):
    h = History(tmp_path / "h.db")
    h.save("1", [("Result", "1")])
    h.clear()
    assert h.fetch() == []
