import os


def data_path(filename: str) -> str:
    data_dir = os.environ.get("API_DATA_DIR", "data").strip() or "data"
    return os.path.join(data_dir, filename)
