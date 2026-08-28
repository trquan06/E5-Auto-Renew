"""Local development entry point."""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"[*] Starting MS365 Auto Renew WebUI from: {PROJECT_DIR}")
    print(f"[*] WebUI URL: http://localhost:{settings.PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        proxy_headers=True,
        forwarded_allow_ips=settings.FORWARDED_ALLOW_IPS,
        reload=settings.DEBUG,
        app_dir=str(PROJECT_DIR),
    )
