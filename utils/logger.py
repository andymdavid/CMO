import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class AgentLogger:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger(agent_name)
        self.logger.setLevel(logging.INFO)
        
        # File handler
        log_file = self.log_dir / f"{agent_name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def log_decision(self, decision_type: str, context: Dict[str, Any], outcome: str):
        """Log agent decisions for audit and learning"""
        decision_log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "decision_type": decision_type,
            "context": context,
            "outcome": outcome
        }
        
        self.logger.info(f"DECISION: {json.dumps(decision_log)}")
    
    def log_api_call(self, service: str, endpoint: str, success: bool, duration: float):
        """Log API calls for monitoring and debugging"""
        api_log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "service": service,
            "endpoint": endpoint,
            "success": success,
            "duration_seconds": duration
        }
        
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, f"API_CALL: {json.dumps(api_log)}")
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Log errors with context"""
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        }
        
        self.logger.error(f"ERROR: {json.dumps(error_log)}")
    
    def log_info(self, message: str, context: Dict[str, Any] = None):
        """Log informational messages"""
        info_log = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "message": message,
            "context": context or {}
        }
        
        self.logger.info(f"INFO: {json.dumps(info_log)}")