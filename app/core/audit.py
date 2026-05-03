import logging
from datetime import datetime

logger = logging.getLogger("audit")

def audit_log(app_id: str, action: str, details: str):
    timestamp = datetime.now().isoformat()
    log_msg = f"[{timestamp}] APP_ID: {app_id} | ACTION: {action} | DETAILS: {details}"
    logger.info(log_msg)
    # Em produção, isso aparecerá nos logs da Square Cloud
    print(log_msg)
