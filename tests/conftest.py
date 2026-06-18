import pytest

from garminscrap import config


class FakeGarmin:
    """Stand-in for garminconnect.Garmin.

    Any get_* call returns a JSON-serializable marker and is recorded.
    Methods named in `fail` raise, to exercise error handling.
    """

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args))
            if name in self.fail:
                raise RuntimeError(f"{name} failed")
            return {"_method": name, "args": list(args)}
        return method


@pytest.fixture
def make_garmin():
    return lambda fail=(): FakeGarmin(fail=fail)


@pytest.fixture
def fake_garmin():
    return FakeGarmin()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path
