import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class FileManager:
    def __init__(self):
        self.data_dir = Path("data")
        self.transcripts_dir = self.data_dir / "transcripts"
        self.research_dir = self.data_dir / "research"
        self.content_dir = self.data_dir / "content"
        self.memory_dir = self.data_dir / "memory"
        
        # Ensure directories exist
        for directory in [self.transcripts_dir, self.research_dir, 
                         self.content_dir / "generated", self.content_dir / "published",
                         self.memory_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def load_transcript(self, transcript_path: str) -> Dict[str, Any]:
        """Load and parse transcript file"""
        path = Path(transcript_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        return {
            "file_path": str(path),
            "file_name": path.name,
            "content": content,
            "word_count": len(content.split()),
            "loaded_at": datetime.now().isoformat()
        }
    
    def save_research_data(self, insight_id: str, research_data: Dict[str, Any]) -> str:
        """Save research findings to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{insight_id}_research.json"
        filepath = self.research_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(research_data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def save_generated_content(self, episode_id: str, content_data: Dict[str, Any]) -> str:
        """Save generated content to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{episode_id}_content.json"
        filepath = self.content_dir / "generated" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def save_published_content(self, episode_id: str, published_data: Dict[str, Any]) -> str:
        """Save published content tracking data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{episode_id}_published.json"
        filepath = self.content_dir / "published" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(published_data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def load_memory(self, agent_name: str) -> Dict[str, Any]:
        """Load agent-specific memory from file system"""
        memory_file = self.memory_dir / f"{agent_name}_memory.json"
        
        if memory_file.exists():
            with open(memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Return default memory structure if file doesn't exist
        return {
            "learnings": {},
            "successful_patterns": [],
            "failed_patterns": [],
            "performance_metrics": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def update_memory(self, agent_name: str, memory_data: Dict[str, Any]):
        """Save updated memory to file system"""
        memory_file = self.memory_dir / f"{agent_name}_memory.json"
        memory_data["last_updated"] = datetime.now().isoformat()
        
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2, ensure_ascii=False)
    
    def load_brand_voice(self) -> Dict[str, Any]:
        """Load brand voice configuration"""
        brand_voice_file = self.memory_dir / "brand_voice.json"
        
        if not brand_voice_file.exists():
            raise FileNotFoundError("Brand voice configuration not found")
        
        with open(brand_voice_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """Load configuration file"""
        config_file = Path("config") / f"{config_name}.json"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_episode_id_from_transcript(self, transcript_path: str) -> str:
        """Extract episode ID from transcript filename"""
        path = Path(transcript_path)
        # Remove extension and clean up filename to create episode ID
        episode_id = path.stem.lower().replace(" ", "_").replace("-", "_")
        return episode_id