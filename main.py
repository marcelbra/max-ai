"""Entry point for max-ai API server."""

import uvicorn

from max_ai.api import app

if __name__ == "__main__":
    uvicorn.run(
        "max_ai.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
