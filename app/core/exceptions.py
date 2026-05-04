class TranscriptException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class TranscriptNotFound(TranscriptException):
    def __init__(self):
        super().__init__("TRANSCRIPT_NOT_FOUND", "Transcript não encontrado", 404)

class BlobExpired(TranscriptException):
    def __init__(self):
        super().__init__("BLOB_EXPIRED", "Transcript expirado", 404)

class ExternalRequestFailed(TranscriptException):
    def __init__(self):
        super().__init__("EXTERNAL_REQUEST_FAILED", "Erro ao buscar blob", 502)
