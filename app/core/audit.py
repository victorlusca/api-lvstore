import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger("audit")

def audit_log(app_id: str, action: str, details: Any, event_type: str = "API_ACTION", status: str = "success", site_user_id: Optional[int] = None):
    """
    Registra um log de auditoria (apenas logger, banco local removido)
    """
    timestamp = datetime.now().isoformat()
    log_msg = f"[{timestamp}] APP_ID: {app_id} | ACTION: {action} | DETAILS: {details}"
    logger.info(log_msg)
    
    # Em produção, isso aparecerá nos logs da Square Cloud
    print(log_msg)
