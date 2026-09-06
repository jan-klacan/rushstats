import pytest


@pytest.fixture
def csv_file(tmp_path):
    def write(text, name="data.csv"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return write
