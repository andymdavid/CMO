#!/usr/bin/env python3
"""
Cost monitoring and reporting tool for the Autonomous Podcast CMO system.
Provides detailed usage analytics and cost projections.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.cost_monitor import CostMonitor


def print_usage_report():
    """Print detailed usage and cost report"""
    
    # Mock config for CostMonitor initialization
    config = {"cost_limits": {}}
    cost_monitor = CostMonitor(config)
    
    summary = cost_monitor.get_usage_summary()
    
    print("🎙️ Autonomous Podcast CMO - Cost Report")
    print("=" * 60)
    
    # Daily Usage
    print(f"\n📅 Daily Usage ({datetime.now().strftime('%Y-%m-%d')})")
    print("-" * 30)
    daily = summary["daily"]
    print(f"  Tokens Used:      {daily['tokens_used']:,} / {daily['tokens_limit']:,}")
    print(f"  Tokens Remaining: {daily['tokens_remaining']:,}")
    print(f"  Usage:            {(daily['tokens_used']/daily['tokens_limit']*100):.1f}%")
    print(f"  Cost Today:       ${daily['cost_usd']:.2f}")
    print(f"  Requests:         {daily['requests']}")
    
    # Monthly Usage
    print(f"\n📊 Monthly Usage ({datetime.now().strftime('%Y-%m')})")
    print("-" * 30)
    monthly = summary["monthly"]
    print(f"  Budget Used:      ${monthly['cost_used_usd']:.2f} / ${monthly['budget_usd']:.2f}")
    print(f"  Budget Remaining: ${monthly['budget_remaining_usd']:.2f}")
    print(f"  Usage:            {(monthly['cost_used_usd']/monthly['budget_usd']*100):.1f}%")
    print(f"  Total Tokens:     {monthly['tokens_used']:,}")
    print(f"  Total Requests:   {monthly['requests']}")
    
    # Recent Episodes
    if summary["recent_episodes"]:
        print(f"\n🎧 Recent Episodes")
        print("-" * 30)
        for episode in summary["recent_episodes"]:
            print(f"  {episode['episode_id']:20} | {episode['tokens']:6,} tokens | ${episode['cost_usd']:.2f}")
    
    # Cost projections
    print(f"\n💰 Cost Projections")
    print("-" * 30)
    
    if daily['tokens_used'] > 0:
        # Project daily cost if we continue at current rate
        daily_rate = daily['cost_usd']
        monthly_projection = daily_rate * 30
        print(f"  If daily usage continues: ${monthly_projection:.2f}/month")
    
    if len(summary["recent_episodes"]) > 0:
        # Average episode cost
        avg_episode_cost = sum(ep['cost_usd'] for ep in summary["recent_episodes"]) / len(summary["recent_episodes"])
        weekly_episodes = 1  # Assume 1 episode per week
        monthly_episode_cost = avg_episode_cost * weekly_episodes * 4.33  # Average weeks per month
        print(f"  Episode average:          ${avg_episode_cost:.2f}/episode")
        print(f"  Monthly (1 ep/week):      ${monthly_episode_cost:.2f}/month")
    
    # Warnings
    print(f"\n⚠️  Status & Warnings")
    print("-" * 30)
    
    daily_usage_pct = (daily['tokens_used'] / daily['tokens_limit']) * 100 if daily['tokens_limit'] > 0 else 0
    monthly_usage_pct = (monthly['cost_used_usd'] / monthly['budget_usd']) * 100 if monthly['budget_usd'] > 0 else 0
    
    if daily_usage_pct > 90:
        print("  🚨 CRITICAL: Daily token limit almost exceeded!")
    elif daily_usage_pct > 75:
        print("  ⚠️  WARNING: High daily token usage")
    else:
        print("  ✅ Daily usage within limits")
    
    if monthly_usage_pct > 90:
        print("  🚨 CRITICAL: Monthly budget almost exceeded!")
    elif monthly_usage_pct > 75:
        print("  ⚠️  WARNING: High monthly usage")
    else:
        print("  ✅ Monthly usage within budget")
    
    print(f"\n📈 Recommendations")
    print("-" * 30)
    
    if daily_usage_pct > 50:
        print("  • Consider reducing max_insights_per_episode")
        print("  • Lower max_tokens per API call")
        print("  • Reduce max_searches_per_insight")
    
    if monthly_usage_pct > 70:
        print("  • Review cost_limits in config/settings.json")
        print("  • Consider processing episodes less frequently")
        print("  • Optimize prompt efficiency")
    
    if len(summary["recent_episodes"]) == 0:
        print("  • No recent episodes processed - system ready to use")
    
    print(f"\n🔧 Configuration File: config/settings.json")
    print(f"📊 Usage Data:       data/memory/api_usage.json")
    print(f"📝 Logs:             logs/cost_monitor.log")


def show_episode_breakdown(episode_id: str):
    """Show detailed breakdown for a specific episode"""
    config = {"cost_limits": {}}
    cost_monitor = CostMonitor(config)
    
    usage_data = cost_monitor.usage_data
    episode_data = usage_data.get("episode_usage", {}).get(episode_id)
    
    if not episode_data:
        print(f"❌ No usage data found for episode: {episode_id}")
        return
    
    print(f"🎧 Episode Breakdown: {episode_id}")
    print("=" * 60)
    
    print(f"Total Cost:   ${episode_data['total_cost_usd']:.2f}")
    print(f"Total Tokens: {episode_data['total_tokens']:,}")
    print(f"Timestamp:    {episode_data['timestamp']}")
    
    print(f"\n🤖 Agent Breakdown:")
    print("-" * 30)
    
    for agent_name, agent_data in episode_data.get("agents", {}).items():
        tokens = agent_data['tokens']
        cost = agent_data['cost_usd']
        pct = (tokens / episode_data['total_tokens']) * 100 if episode_data['total_tokens'] > 0 else 0
        print(f"  {agent_name:20} | {tokens:6,} tokens | ${cost:6.2f} | {pct:5.1f}%")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--episode" and len(sys.argv) > 2:
            show_episode_breakdown(sys.argv[2])
        elif sys.argv[1] in ["--help", "-h"]:
            print("""
Cost Reporting Tool

Usage:
    python scripts/cost_report.py                    # Show overall usage report
    python scripts/cost_report.py --episode <id>     # Show episode breakdown
    python scripts/cost_report.py --help             # Show this help

Examples:
    python scripts/cost_report.py
    python scripts/cost_report.py --episode test_episode
            """)
        else:
            print(f"❌ Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        print_usage_report()


if __name__ == "__main__":
    main()