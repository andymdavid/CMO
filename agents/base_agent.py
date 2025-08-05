from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils.logger import AgentLogger
from utils.file_manager import FileManager


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the podcast CMO system.
    Provides common functionality for logging, memory management, and file operations.
    """
    
    def __init__(self, agent_name: str, config: Dict[str, Any]):
        self.agent_name = agent_name
        self.config = config
        self.logger = AgentLogger(agent_name)
        self.file_manager = FileManager()
        self.memory = self.load_memory()
        
        self.logger.log_info(f"Initialized {agent_name} agent", {"config_keys": list(config.keys())})
    
    def load_memory(self) -> Dict[str, Any]:
        """Load agent-specific memory from file system"""
        try:
            memory = self.file_manager.load_memory(self.agent_name)
            self.logger.log_info("Memory loaded successfully", {"memory_keys": list(memory.keys())})
            return memory
        except Exception as e:
            self.logger.log_error("memory_load_failed", str(e))
            return self._get_default_memory()
    
    def save_memory(self, memory_data: Optional[Dict[str, Any]] = None):
        """Save updated memory to file system"""
        try:
            data_to_save = memory_data if memory_data is not None else self.memory
            self.file_manager.update_memory(self.agent_name, data_to_save)
            self.logger.log_info("Memory saved successfully")
        except Exception as e:
            self.logger.log_error("memory_save_failed", str(e))
    
    def log_decision(self, decision_type: str, context: Dict[str, Any], outcome: str):
        """Log agent decisions for audit and learning"""
        self.logger.log_decision(decision_type, context, outcome)
        
        # Update memory with decision patterns
        if "decisions" not in self.memory:
            self.memory["decisions"] = []
        
        self.memory["decisions"].append({
            "decision_type": decision_type,
            "context": context,
            "outcome": outcome,
            "timestamp": self.logger.logger.handlers[0].format(
                self.logger.logger.makeRecord(
                    self.logger.logger.name, 20, "", 0, "", (), None
                )
            ).split(" - ")[0]
        })
        
        # Keep only recent decisions (last 100)
        if len(self.memory["decisions"]) > 100:
            self.memory["decisions"] = self.memory["decisions"][-100:]
    
    def update_performance_metrics(self, metric_name: str, metric_value: Any):
        """Update performance metrics in memory"""
        if "performance_metrics" not in self.memory:
            self.memory["performance_metrics"] = {}
        
        self.memory["performance_metrics"][metric_name] = metric_value
        self.logger.log_info(f"Updated metric: {metric_name}", {"value": metric_value})
    
    def learn_from_success(self, pattern: Dict[str, Any]):
        """Record successful patterns for future learning"""
        if "successful_patterns" not in self.memory:
            self.memory["successful_patterns"] = []
        
        self.memory["successful_patterns"].append(pattern)
        self.logger.log_info("Recorded successful pattern", pattern)
    
    def learn_from_failure(self, pattern: Dict[str, Any]):
        """Record failed patterns to avoid in future"""
        if "failed_patterns" not in self.memory:
            self.memory["failed_patterns"] = []
        
        self.memory["failed_patterns"].append(pattern)
        self.logger.log_info("Recorded failed pattern", pattern)
    
    def _get_default_memory(self) -> Dict[str, Any]:
        """Get default memory structure for the agent"""
        return {
            "learnings": {},
            "successful_patterns": [],
            "failed_patterns": [],
            "performance_metrics": {},
            "decisions": [],
            "last_updated": None
        }
    
    @abstractmethod
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process assigned task and return results.
        Must be implemented by all concrete agent classes.
        """
        pass
    
    @abstractmethod
    def validate_input(self, task: Dict[str, Any]) -> bool:
        """
        Validate task input before processing.
        Must be implemented by all concrete agent classes.
        """
        pass
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and health information"""
        return {
            "agent_name": self.agent_name,
            "memory_loaded": bool(self.memory),
            "config_loaded": bool(self.config),
            "recent_decisions": len(self.memory.get("decisions", [])),
            "performance_metrics": self.memory.get("performance_metrics", {}),
            "last_memory_update": self.memory.get("last_updated")
        }