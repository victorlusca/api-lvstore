import os
import uvicorn
from dotenv import load_dotenv

# Load .env for local development
load_dotenv()

if __name__ == "__main__":
    # Square Cloud uses 'PORT' environment variable
    # If not present, default to 8000
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "app.main:app", 
        host=host, 
        port=port, 
        reload=os.environ.get("API_DEBUG") == "1"
    )
