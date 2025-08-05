#!/usr/bin/env python3
"""
Cost comparison tool showing savings from OpenRouter integration.
Demonstrates the cost difference between Claude-only and hybrid routing.
"""

import json
from pathlib import Path
from typing import Dict, Any


def calculate_episode_costs() -> Dict[str, Any]:
    """Calculate expected costs per episode with different configurations"""
    
    # Typical token usage per episode
    token_usage = {
        "cmo_orchestrator": {
            "insight_extraction": 4000,      # Claude (reasoning)
            "insight_prioritization": 3000   # Claude (reasoning)
        },
        "research_agent": {
            "query_generation": 1000,        # OpenRouter (content)
            "analysis": 2500                 # Claude (reasoning)
        },
        "content_agent": {
            "framework_threads": 2000,       # OpenRouter (content)
            "contrarian_content": 1500,      # OpenRouter (content)
            "case_study_content": 1000,      # OpenRouter (content)
            "tactical_content": 1200,        # OpenRouter (content)
            "brand_validation": 800          # Claude (reasoning)
        },
        "publishing_agent": {
            "scheduling": 500                # Minimal
        }
    }
    
    # Pricing per 1M tokens
    claude_pricing = {
        "input": 3.00,   # $3 per 1M input tokens
        "output": 15.00  # $15 per 1M output tokens
    }
    
    openrouter_deepseek_pricing = {
        "input": 0.14,   # $0.14 per 1M input tokens
        "output": 0.28   # $0.28 per 1M output tokens
    }
    
    # Calculate costs
    
    # Claude-only scenario
    claude_only_total = 0
    for agent, tasks in token_usage.items():
        for task, tokens in tasks.items():
            # Assume 70% input, 30% output tokens
            input_tokens = tokens * 0.7
            output_tokens = tokens * 0.3
            
            cost = (input_tokens * claude_pricing["input"] / 1000000) + \
                   (output_tokens * claude_pricing["output"] / 1000000)
            claude_only_total += cost
    
    # Hybrid routing scenario
    hybrid_total = 0
    claude_tasks = [
        ("cmo_orchestrator", "insight_extraction"),
        ("cmo_orchestrator", "insight_prioritization"),
        ("research_agent", "analysis"),
        ("content_agent", "brand_validation")
    ]
    
    openrouter_tasks = [
        ("research_agent", "query_generation"),
        ("content_agent", "framework_threads"),
        ("content_agent", "contrarian_content"),
        ("content_agent", "case_study_content"),
        ("content_agent", "tactical_content")
    ]
    
    # Calculate Claude costs in hybrid
    for agent, task in claude_tasks:
        tokens = token_usage[agent][task]
        input_tokens = tokens * 0.7
        output_tokens = tokens * 0.3
        
        cost = (input_tokens * claude_pricing["input"] / 1000000) + \
               (output_tokens * claude_pricing["output"] / 1000000)
        hybrid_total += cost
    
    # Calculate OpenRouter costs in hybrid
    for agent, task in openrouter_tasks:
        tokens = token_usage[agent][task]
        input_tokens = tokens * 0.7
        output_tokens = tokens * 0.3
        
        cost = (input_tokens * openrouter_deepseek_pricing["input"] / 1000000) + \
               (output_tokens * openrouter_deepseek_pricing["output"] / 1000000)
        hybrid_total += cost
    
    # Add minimal publishing costs
    hybrid_total += (500 * 0.7 * claude_pricing["input"] / 1000000) + \
                   (500 * 0.3 * claude_pricing["output"] / 1000000)
    
    # Calculate savings
    savings_per_episode = claude_only_total - hybrid_total
    savings_percentage = (savings_per_episode / claude_only_total) * 100
    
    return {
        "claude_only": {
            "cost_per_episode": claude_only_total,
            "cost_per_month": claude_only_total * 4.33,  # ~4.33 weeks per month
            "tokens_per_episode": sum(sum(tasks.values()) for tasks in token_usage.values())
        },
        "hybrid_routing": {
            "cost_per_episode": hybrid_total,
            "cost_per_month": hybrid_total * 4.33,
            "claude_tokens": sum(token_usage[agent][task] for agent, task in claude_tasks) + 1300,  # +validation+publishing
            "openrouter_tokens": sum(token_usage[agent][task] for agent, task in openrouter_tasks)
        },
        "savings": {
            "per_episode": savings_per_episode,
            "per_month": savings_per_episode * 4.33,
            "percentage": savings_percentage
        },
        "task_routing": {
            "claude_tasks": claude_tasks,
            "openrouter_tasks": openrouter_tasks
        }
    }


def print_cost_comparison():
    """Print detailed cost comparison"""
    
    costs = calculate_episode_costs()
    
    print("🎙️ Autonomous Podcast CMO - Cost Comparison")
    print("=" * 70)
    
    print(f"\n💰 Claude-Only Configuration")
    print("-" * 40)
    print(f"  Cost per episode:  ${costs['claude_only']['cost_per_episode']:.2f}")
    print(f"  Cost per month:    ${costs['claude_only']['cost_per_month']:.2f}")
    print(f"  Tokens per episode: {costs['claude_only']['tokens_per_episode']:,}")
    
    print(f"\n🚀 Hybrid Routing (Claude + OpenRouter)")
    print("-" * 40)
    print(f"  Cost per episode:  ${costs['hybrid_routing']['cost_per_episode']:.2f}")
    print(f"  Cost per month:    ${costs['hybrid_routing']['cost_per_month']:.2f}")
    print(f"  Claude tokens:     {costs['hybrid_routing']['claude_tokens']:,}")
    print(f"  OpenRouter tokens: {costs['hybrid_routing']['openrouter_tokens']:,}")
    
    print(f"\n💸 Cost Savings")
    print("-" * 40)
    print(f"  Savings per episode: ${costs['savings']['per_episode']:.2f}")
    print(f"  Savings per month:   ${costs['savings']['per_month']:.2f}")
    print(f"  Percentage saved:    {costs['savings']['percentage']:.1f}%")
    
    print(f"\n🧠 Task Routing Strategy")
    print("-" * 40)
    print(f"  Claude (High Complexity):")
    for agent, task in costs['task_routing']['claude_tasks']:
        print(f"    • {agent}: {task}")
    
    print(f"  OpenRouter/DeepSeek (Content Generation):")
    for agent, task in costs['task_routing']['openrouter_tasks']:
        print(f"    • {agent}: {task}")
    
    print(f"\n📊 Annual Projections (1 episode/week)")
    print("-" * 40)
    annual_claude = costs['claude_only']['cost_per_month'] * 12
    annual_hybrid = costs['hybrid_routing']['cost_per_month'] * 12
    annual_savings = costs['savings']['per_month'] * 12
    
    print(f"  Claude-only:    ${annual_claude:.2f}/year")
    print(f"  Hybrid routing: ${annual_hybrid:.2f}/year")
    print(f"  Annual savings: ${annual_savings:.2f}/year ({costs['savings']['percentage']:.1f}%)")
    
    print(f"\n⚡ Key Benefits")
    print("-" * 40)
    print(f"  • {costs['savings']['percentage']:.0f}% cost reduction for content generation")
    print(f"  • Claude reserved for strategic reasoning tasks")
    print(f"  • DeepSeek handles creative content generation")
    print(f"  • Maintained quality with intelligent routing")
    print(f"  • Automatic fallback to Claude if OpenRouter fails")
    
    print(f"\n🔧 Configuration")
    print("-" * 40)
    print(f"  • Add OPENROUTER_API_KEY to config/api_keys.env")
    print(f"  • Set 'enable_openrouter': true in config/settings.json")
    print(f"  • System automatically routes tasks optimally")
    
    print(f"\n💡 Recommendation")
    print("-" * 40)
    if costs['savings']['percentage'] > 80:
        print(f"  🚀 HIGHLY RECOMMENDED: {costs['savings']['percentage']:.0f}% cost savings!")
        print(f"     Save ${costs['savings']['per_month']:.2f}/month with OpenRouter integration")
    else:
        print(f"  ✅ Recommended: {costs['savings']['percentage']:.0f}% cost savings")
    
    print(f"\n📈 Setup Instructions")
    print("-" * 40)
    print(f"  1. Get OpenRouter API key: https://openrouter.ai/")
    print(f"  2. Add to config/api_keys.env: OPENROUTER_API_KEY=your_key")
    print(f"  3. Run: python main.py --status")
    print(f"  4. Process episode: python main.py data/transcripts/episode.txt")


if __name__ == "__main__":
    print_cost_comparison()