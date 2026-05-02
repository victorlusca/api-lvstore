import os

import uvicorn


if __name__ == "__main__":
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    uvicorn.run("app.app:app", host=host, port=port, reload=os.environ.get("API_DEBUG") == "1")
