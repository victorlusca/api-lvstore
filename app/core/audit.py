import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger("audit")

def audit_log(
    action: str, 
    details: Any, 
    app_id: Optional[str] = None, 
    event_type: str = "API_ACTION", 
    status: str = "success", 
    site_user_id: Optional[int] = None,
    **kwargs # Captura argumentos extras como guild_id, actor_discord_id, etc.
):
    """
    Registra um log de auditoria (apenas logger, banco local removido)
    """
    timestamp = datetime.now().isoformat()
    app_id_str = f"APP_ID: {app_id} | " if app_id else ""
    log_msg = f"[{timestamp}] {app_id_str}ACTION: {action} | DETAILS: {details}"
    
    # Adiciona kwargs ao log se existirem
    if kwargs:
        log_msg += f" | EXTRA: {kwargs}"
        
    logger.info(log_msg)
    
    # Em produção, isso aparecerá nos logs da Square Cloud
    print(log_msg)

# Alias para compatibilidade com o código antigo que usava log_audit
log_audit = audit_log
