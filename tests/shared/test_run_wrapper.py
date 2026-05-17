import runpy


def test_run_py_delegates_to_package_main(monkeypatch):
    called = {"value": False}

    def _fake_main():
        called["value"] = True

    monkeypatch.setattr("crypto_news_analyzer.main.main", _fake_main)

    runpy.run_path("run.py", run_name="__main__")

    assert called["value"] is True
