import os


def data_path(filename: str) -> str:
    data_dir = os.environ.get("API_DATA_DIR", "data").strip() or "data"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)
