import logging
from datetime import datetime
from typing import Optional, Any
from app.security.audit import log_audit

logger = logging.getLogger("audit")

def audit_log(app_id: str, action: str, details: Any, event_type: str = "API_ACTION", status: str = "success", site_user_id: Optional[int] = None):
    """
    Registra um log de auditoria no banco de dados master_data.db
    """
    timestamp = datetime.now().isoformat()
    log_msg = f"[{timestamp}] APP_ID: {app_id} | ACTION: {action} | DETAILS: {details}"
    logger.info(log_msg)
    
    # Registra no banco de dados SQLite
    try:
        log_audit(
            event_type=event_type,
            system_key="API",
            action_key=action,
            bot_id=int(app_id) if app_id.isdigit() else None,
            details=details,
            status=status,
            message=str(details)[:1000] if isinstance(details, str) else None,
            source="api",
            site_user_id=site_user_id
        )
    except Exception as e:
        logger.error(f"Erro ao registrar log de auditoria: {e}")
    
    # Em produção, isso aparecerá nos logs da Square Cloud
    print(log_msg)
