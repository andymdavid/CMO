#!/usr/bin/env python3
"""
Main application runner for the Autonomous Podcast CMO system.
Processes podcast transcripts and generates social media content autonomously.
"""

import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.cmo_orchestrator import CMOOrchestrator
from agents.research_agent import ResearchAgent
from agents.content_agent import ContentAgent
from agents.publishing_agent import PublishingAgent
from utils.file_manager import FileManager
from utils.logger import AgentLogger


def load_config() -> dict:
    """Load system configuration and API keys"""
    try:
        # Load environment variables
        load_dotenv('config/api_keys.env')
        
        # Load settings
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        
        # Add API keys from environment
        config.update({
            "claude_api_key": os.getenv("CLAUDE_API_KEY"),
            "typefully_api_key": os.getenv("TYPEFULLY_API_KEY")
        })
        
        # Validate required API keys
        if not config["claude_api_key"]:
            raise ValueError("CLAUDE_API_KEY not found in environment variables")
        if not config["typefully_api_key"]:
            print("Warning: TYPEFULLY_API_KEY not found - publishing will be simulated")
        
        return config
        
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Configuration file not found: {e}")
    except Exception as e:
        raise Exception(f"Failed to load configuration: {e}")


def initialize_agents(config: dict) -> dict:
    """Initialize all agents with dependencies"""
    logger = AgentLogger("main_app")
    logger.log_info("Initializing agents", {"config_loaded": True})
    
    try:
        # Initialize specialist agents
        research_agent = ResearchAgent(config)
        content_agent = ContentAgent(config)
        publishing_agent = PublishingAgent(config)
        
        # Initialize CMO orchestrator with agent dependencies
        cmo_agent = CMOOrchestrator(config)
        cmo_agent.research_agent = research_agent
        cmo_agent.content_agent = content_agent
        cmo_agent.publishing_agent = publishing_agent
        
        agents = {
            "cmo": cmo_agent,
            "research": research_agent,
            "content": content_agent,
            "publishing": publishing_agent
        }
        
        logger.log_info("All agents initialized successfully", 
                       {"agent_count": len(agents)})
        
        return agents
        
    except Exception as e:
        logger.log_error("agent_initialization_error", str(e))
        raise Exception(f"Failed to initialize agents: {e}")


def validate_transcript_file(transcript_path: str) -> bool:
    """Validate transcript file exists and is readable"""
    path = Path(transcript_path)
    
    if not path.exists():
        print(f"❌ Error: Transcript file not found: {transcript_path}")
        return False
    
    if not path.is_file():
        print(f"❌ Error: Path is not a file: {transcript_path}")
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if len(content) < 100:  # Minimum viable transcript length
                print(f"❌ Error: Transcript appears too short (< 100 characters)")
                return False
    except Exception as e:
        print(f"❌ Error: Cannot read transcript file: {e}")
        return False
    
    return True


def process_episode(transcript_path: str) -> bool:
    """
    Main entry point for processing a podcast episode
    Returns True if successful, False if failed
    """
    logger = AgentLogger("main_app")
    
    print(f"🎙️  Processing episode: {transcript_path}")
    print("=" * 60)
    
    try:
        # Validate transcript file
        if not validate_transcript_file(transcript_path):
            return False
        
        # Load configuration
        print("📋 Loading configuration...")
        config = load_config()
        print("✅ Configuration loaded successfully")
        
        # Initialize agents
        print("🤖 Initializing agents...")
        agents = initialize_agents(config)
        print("✅ All agents initialized")
        
        # Show cost limits
        cost_limits = config.get("cost_limits", {})
        if cost_limits.get("enable_cost_monitoring", True):
            print(f"💰 Cost Protection Active:")
            print(f"   • Daily limit: {cost_limits.get('daily_token_limit', 30000):,} tokens")
            print(f"   • Episode limit: {cost_limits.get('episode_token_limit', 15000):,} tokens") 
            print(f"   • Monthly budget: ${cost_limits.get('monthly_budget_usd', 50)}")
        
        # Process transcript through CMO orchestrator
        print("🔄 Processing transcript...")
        results = agents["cmo"].process_transcript(transcript_path)
        
        # Display results
        print("\n🎉 Episode processed successfully!")
        print("=" * 60)
        
        pipeline_results = results.get("content_pipeline_results", [])
        successful_results = [r for r in pipeline_results if r.get("status") == "completed"]
        failed_results = [r for r in pipeline_results if r.get("status") == "failed"]
        
        print(f"📊 Processing Summary:")
        print(f"   • Episode ID: {results.get('episode_id', 'unknown')}")
        print(f"   • Insights extracted: {results.get('insights_extracted', 0)}")
        print(f"   • Insights processed: {results.get('insights_processed', 0)}")
        print(f"   • Successful content pipelines: {len(successful_results)}")
        print(f"   • Failed content pipelines: {len(failed_results)}")
        
        # Count total content pieces
        total_content_pieces = 0
        total_scheduled = 0
        
        for result in successful_results:
            content_pieces = result.get("content", {}).get("content_pieces", [])
            total_content_pieces += len(content_pieces)
            
            publishing_result = result.get("publishing", {})
            scheduled_content = publishing_result.get("scheduled_content", [])
            total_scheduled += len(scheduled_content)
        
        print(f"   • Total content pieces generated: {total_content_pieces}")
        print(f"   • Content pieces scheduled: {total_scheduled}")
        
        if failed_results:
            print(f"\n⚠️  {len(failed_results)} insights failed processing:")
            for failed in failed_results:
                insight_title = failed.get("insight", {}).get("title", "Unknown")
                error = failed.get("error", "Unknown error")
                print(f"   • {insight_title}: {error}")
        
        print(f"\n📅 Content scheduled for publication via Typefully")
        print(f"📁 Results saved to: data/content/generated/")
        
        logger.log_info("Episode processing completed successfully", 
                       {"episode_id": results.get("episode_id"),
                        "successful_pipelines": len(successful_results),
                        "total_content_pieces": total_content_pieces})
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Error processing episode: {error_msg}")
        logger.log_error("episode_processing_error", error_msg, 
                         {"transcript_path": transcript_path})
        return False


def show_system_status():
    """Display current system status and health"""
    print("🔍 System Status Check")
    print("=" * 40)
    
    try:
        # Check configuration
        config = load_config()
        print("✅ Configuration loaded")
        
        # Check agents can be initialized
        agents = initialize_agents(config)
        print("✅ All agents operational")
        
        # Check file system
        file_manager = FileManager()
        print("✅ File system ready")
        
        # Check API connectivity (basic validation)
        if config.get("claude_api_key"):
            print("✅ Claude API key configured")
        else:
            print("❌ Claude API key missing")
            
        if config.get("typefully_api_key"):
            print("✅ Typefully API key configured")
        else:
            print("⚠️  Typefully API key missing (publishing will be simulated)")
        
        # Check directory structure
        required_dirs = ["data/transcripts", "data/content/generated", "data/content/published", 
                        "data/research", "data/memory", "logs"]
        
        for dir_path in required_dirs:
            if Path(dir_path).exists():
                print(f"✅ Directory exists: {dir_path}")
            else:
                print(f"❌ Missing directory: {dir_path}")
        
        print("\n🎯 System ready for transcript processing!")
        
    except Exception as e:
        print(f"❌ System status check failed: {e}")


def show_usage():
    """Show usage instructions"""
    print("""
🎙️ Autonomous Podcast CMO System

Usage:
    python main.py <transcript_file_path>    # Process a podcast transcript
    python main.py --status                  # Check system status
    python main.py --cost-report             # Show cost usage report
    python main.py --help                    # Show this help message

Examples:
    python main.py data/transcripts/episode_047.txt
    python main.py /path/to/transcript.txt
    
Setup:
    1. Copy config/api_keys.env.example to config/api_keys.env
    2. Add your Claude and Typefully API keys
    3. Place transcript files in data/transcripts/
    4. Run: python main.py data/transcripts/your_transcript.txt

Cost Management:
    • Default limits: 30k tokens/day, $50/month
    • Configure in config/settings.json under 'cost_limits'
    • View usage: python main.py --cost-report

For more information, see README.md
    """)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)
    
    arg = sys.argv[1]
    
    if arg in ["--help", "-h"]:
        show_usage()
        sys.exit(0)
    elif arg in ["--status", "-s"]:
        show_system_status()
        sys.exit(0)
    elif arg in ["--cost-report", "--cost", "-c"]:
        from scripts.cost_report import print_usage_report
        print_usage_report()
        sys.exit(0)
    elif arg.startswith("--"):
        print(f"❌ Unknown option: {arg}")
        show_usage()
        sys.exit(1)
    else:
        # Process transcript file
        transcript_path = arg
        success = process_episode(transcript_path)
        
        if success:
            print("\n🎉 Processing completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Processing failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()