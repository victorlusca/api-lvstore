import os


def data_path(filename: str) -> str:
    # Ajustado para buscar os dados no diretório do bot (sistema-bot-corp)
    default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sistema-bot-corp", "data"))
    data_dir = os.environ.get("API_DATA_DIR", default_path).strip() or default_path
    return os.path.join(data_dir, filename)
