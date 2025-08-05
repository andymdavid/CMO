"""
Cost monitoring and budget protection for API usage.
Prevents bill shock by tracking usage and enforcing limits.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import AgentLogger


class CostMonitor:
    """Monitor and limit API usage costs to prevent bill shock"""
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = AgentLogger("cost_monitor")
        self.config = config.get("cost_limits", {})
        
        # Cost tracking file
        self.usage_file = Path("data/memory/api_usage.json")
        self.usage_file.parent.mkdir(exist_ok=True)
        
        # Default limits (configurable)
        self.daily_token_limit = self.config.get("daily_token_limit", 50000)  # ~$10-20/day
        self.episode_token_limit = self.config.get("episode_token_limit", 25000)  # ~$5-10/episode
        self.monthly_budget_usd = self.config.get("monthly_budget_usd", 100)
        
        # Pricing (Claude 3.5 Sonnet approximate)
        self.input_token_cost = 0.000003  # $3 per 1M input tokens
        self.output_token_cost = 0.000015  # $15 per 1M output tokens
        
        self.usage_data = self.load_usage_data()
    
    def load_usage_data(self) -> Dict[str, Any]:
        """Load existing usage data"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    # Clean old data (older than 31 days)
                    self.clean_old_data(data)
                    return data
            except Exception as e:
                self.logger.log_error("usage_data_load_error", str(e))
        
        return {
            "daily_usage": {},
            "episode_usage": {},
            "monthly_totals": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def clean_old_data(self, data: Dict[str, Any]):
        """Remove usage data older than 31 days"""
        cutoff_date = datetime.now() - timedelta(days=31)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        # Clean daily usage
        daily_usage = data.get("daily_usage", {})
        data["daily_usage"] = {
            date: usage for date, usage in daily_usage.items()
            if date >= cutoff_str
        }
        
        # Clean episode usage (keep last 50 episodes)
        episode_usage = data.get("episode_usage", {})
        if len(episode_usage) > 50:
            sorted_episodes = sorted(episode_usage.items(), 
                                   key=lambda x: x[1].get("timestamp", ""), 
                                   reverse=True)
            data["episode_usage"] = dict(sorted_episodes[:50])
    
    def check_pre_request_limits(self, agent_name: str, estimated_tokens: int, 
                                episode_id: Optional[str] = None) -> Dict[str, Any]:
        """Check if request would exceed limits BEFORE making API call"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")
        
        # Get current usage
        daily_tokens = self.usage_data["daily_usage"].get(today, {}).get("total_tokens", 0)
        episode_tokens = 0
        if episode_id:
            episode_tokens = self.usage_data["episode_usage"].get(episode_id, {}).get("total_tokens", 0)
        
        monthly_cost = self.usage_data["monthly_totals"].get(current_month, {}).get("total_cost_usd", 0)
        
        # Check limits
        daily_would_exceed = (daily_tokens + estimated_tokens) > self.daily_token_limit
        episode_would_exceed = episode_id and (episode_tokens + estimated_tokens) > self.episode_token_limit
        
        # Estimate cost
        estimated_cost = estimated_tokens * self.input_token_cost
        monthly_would_exceed = (monthly_cost + estimated_cost) > self.monthly_budget_usd
        
        result = {
            "allowed": True,
            "reasons": [],
            "current_usage": {
                "daily_tokens": daily_tokens,
                "episode_tokens": episode_tokens,
                "monthly_cost_usd": round(monthly_cost, 2)
            },
            "limits": {
                "daily_token_limit": self.daily_token_limit,
                "episode_token_limit": self.episode_token_limit,
                "monthly_budget_usd": self.monthly_budget_usd
            },
            "estimated_cost_usd": round(estimated_cost, 4)
        }
        
        # Check each limit
        if daily_would_exceed:
            result["allowed"] = False
            result["reasons"].append(f"Daily token limit would be exceeded: {daily_tokens + estimated_tokens} > {self.daily_token_limit}")
        
        if episode_would_exceed:
            result["allowed"] = False
            result["reasons"].append(f"Episode token limit would be exceeded: {episode_tokens + estimated_tokens} > {self.episode_token_limit}")
        
        if monthly_would_exceed:
            result["allowed"] = False
            result["reasons"].append(f"Monthly budget would be exceeded: ${monthly_cost + estimated_cost:.2f} > ${self.monthly_budget_usd}")
        
        if not result["allowed"]:
            self.logger.log_error("cost_limit_exceeded", 
                                f"Request blocked - would exceed limits", 
                                {"agent": agent_name, "reasons": result["reasons"]})
        
        return result
    
    def record_api_usage(self, agent_name: str, input_tokens: int, output_tokens: int, 
                        episode_id: Optional[str] = None, success: bool = True):
        """Record actual API usage after request completes"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")
        timestamp = datetime.now().isoformat()
        
        # Calculate costs
        input_cost = input_tokens * self.input_token_cost
        output_cost = output_tokens * self.output_token_cost
        total_cost = input_cost + output_cost
        total_tokens = input_tokens + output_tokens
        
        # Update daily usage
        if today not in self.usage_data["daily_usage"]:
            self.usage_data["daily_usage"][today] = {
                "total_tokens": 0,
                "total_cost_usd": 0,
                "requests": 0,
                "agents": {}
            }
        
        daily = self.usage_data["daily_usage"][today]
        daily["total_tokens"] += total_tokens
        daily["total_cost_usd"] += total_cost
        daily["requests"] += 1
        
        if agent_name not in daily["agents"]:
            daily["agents"][agent_name] = {"tokens": 0, "cost_usd": 0, "requests": 0}
        
        daily["agents"][agent_name]["tokens"] += total_tokens
        daily["agents"][agent_name]["cost_usd"] += total_cost
        daily["agents"][agent_name]["requests"] += 1
        
        # Update episode usage
        if episode_id:
            if episode_id not in self.usage_data["episode_usage"]:
                self.usage_data["episode_usage"][episode_id] = {
                    "total_tokens": 0,
                    "total_cost_usd": 0,
                    "agents": {},
                    "timestamp": timestamp
                }
            
            episode = self.usage_data["episode_usage"][episode_id]
            episode["total_tokens"] += total_tokens
            episode["total_cost_usd"] += total_cost
            
            if agent_name not in episode["agents"]:
                episode["agents"][agent_name] = {"tokens": 0, "cost_usd": 0}
            
            episode["agents"][agent_name]["tokens"] += total_tokens
            episode["agents"][agent_name]["cost_usd"] += total_cost
        
        # Update monthly totals
        if current_month not in self.usage_data["monthly_totals"]:
            self.usage_data["monthly_totals"][current_month] = {
                "total_tokens": 0,
                "total_cost_usd": 0,
                "requests": 0
            }
        
        monthly = self.usage_data["monthly_totals"][current_month]
        monthly["total_tokens"] += total_tokens
        monthly["total_cost_usd"] += total_cost
        monthly["requests"] += 1
        
        # Update timestamp
        self.usage_data["last_updated"] = timestamp
        
        # Save usage data
        self.save_usage_data()
        
        # Log usage
        self.logger.log_info("api_usage_recorded", {
            "agent": agent_name,
            "episode_id": episode_id,
            "tokens": total_tokens,
            "cost_usd": round(total_cost, 4),
            "success": success
        })
        
        # Check if approaching limits
        self.check_usage_warnings(agent_name)
    
    def save_usage_data(self):
        """Save usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            self.logger.log_error("usage_data_save_error", str(e))
    
    def check_usage_warnings(self, agent_name: str):
        """Check if usage is approaching limits and warn"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")
        
        daily_tokens = self.usage_data["daily_usage"].get(today, {}).get("total_tokens", 0)
        monthly_cost = self.usage_data["monthly_totals"].get(current_month, {}).get("total_cost_usd", 0)
        
        # Daily warning at 80%
        if daily_tokens > self.daily_token_limit * 0.8:
            self.logger.log_info("daily_usage_warning", {
                "agent": agent_name,
                "current_tokens": daily_tokens,
                "limit": self.daily_token_limit,
                "percentage": round((daily_tokens / self.daily_token_limit) * 100, 1)
            })
        
        # Monthly warning at 80%
        if monthly_cost > self.monthly_budget_usd * 0.8:
            self.logger.log_info("monthly_budget_warning", {
                "agent": agent_name,
                "current_cost": round(monthly_cost, 2),
                "budget": self.monthly_budget_usd,
                "percentage": round((monthly_cost / self.monthly_budget_usd) * 100, 1)
            })
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")
        
        daily_usage = self.usage_data["daily_usage"].get(today, {})
        monthly_usage = self.usage_data["monthly_totals"].get(current_month, {})
        
        return {
            "daily": {
                "tokens_used": daily_usage.get("total_tokens", 0),
                "tokens_limit": self.daily_token_limit,
                "tokens_remaining": max(0, self.daily_token_limit - daily_usage.get("total_tokens", 0)),
                "cost_usd": round(daily_usage.get("total_cost_usd", 0), 2),
                "requests": daily_usage.get("requests", 0)
            },
            "monthly": {
                "cost_used_usd": round(monthly_usage.get("total_cost_usd", 0), 2),
                "budget_usd": self.monthly_budget_usd,
                "budget_remaining_usd": round(max(0, self.monthly_budget_usd - monthly_usage.get("total_cost_usd", 0)), 2),
                "tokens_used": monthly_usage.get("total_tokens", 0),
                "requests": monthly_usage.get("requests", 0)
            },
            "recent_episodes": [
                {
                    "episode_id": episode_id,
                    "tokens": data["total_tokens"],
                    "cost_usd": round(data["total_cost_usd"], 2)
                }
                for episode_id, data in sorted(
                    self.usage_data["episode_usage"].items(),
                    key=lambda x: x[1].get("timestamp", ""),
                    reverse=True
                )[:5]
            ]
        }