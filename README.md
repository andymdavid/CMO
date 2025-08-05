# Autonomous Podcast CMO System

An AI-powered system that transforms podcast transcripts into engaging social media content automatically. Built for "The Good Stuff" podcast, this system extracts business insights, researches supporting evidence, and generates brand-consistent social media content.

## 🎯 Overview

The system uses a multi-agent architecture to:
- **Extract** key business insights from podcast transcripts
- **Research** supporting evidence and case studies  
- **Generate** social media content (Twitter threads, tweets, quote tweets)
- **Schedule** content publication via Typefully
- **Learn** from performance to improve over time

## 🏗️ Architecture

### Core Agents
- **CMO Orchestrator**: Coordinates the entire pipeline and manages workflow
- **Research Agent**: Finds supporting evidence and SME case studies
- **Content Agent**: Generates brand-consistent social media content
- **Publishing Agent**: Handles scheduling and publication via Typefully

### Key Features
- **Brand Voice Consistency**: Maintains Pete & Andy's contrarian, framework-driven style
- **Autonomous Operation**: Minimal human intervention required
- **Quality Validation**: Content undergoes brand voice and quality checks
- **Error Recovery**: Robust error handling and retry mechanisms
- **Performance Learning**: System improves based on content performance

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Claude Pro account with API access
- Typefully account (free tier works)
- OpenRouter account (optional, for 90% cost savings)

### Installation

1. **Clone and setup project**:
```bash
git clone <repository-url>
cd TGS_CMO
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure API keys**:
```bash
cp config/api_keys.env.example config/api_keys.env
# Edit config/api_keys.env with your actual API keys:
# CLAUDE_API_KEY=your_claude_api_key_here
# TYPEFULLY_API_KEY=your_typefully_api_key_here
# OPENROUTER_API_KEY=your_openrouter_api_key_here  # Optional, for cost savings
```

3. **Test the system**:
```bash
python main.py --status
```

### Process Your First Episode

1. **Add transcript**:
```bash
# Place your podcast transcript in data/transcripts/
cp your_transcript.txt data/transcripts/episode_001.txt
```

2. **Process the episode**:
```bash
python main.py data/transcripts/episode_001.txt
```

3. **Review results**:
- Generated content: `data/content/generated/`
- Publishing schedule: Check Typefully dashboard
- System logs: `logs/`

## 📁 Project Structure

```
TGS_CMO/
├── agents/                    # Core agent implementations
│   ├── base_agent.py         # Shared agent functionality
│   ├── cmo_orchestrator.py   # Main coordinator
│   ├── research_agent.py     # Web research and data gathering
│   ├── content_agent.py      # Content generation
│   └── publishing_agent.py   # Typefully integration
├── config/                   # Configuration files
│   ├── settings.json         # System settings
│   ├── api_keys.env         # API keys (not in git)
│   └── prompts/             # AI prompt templates
├── data/                    # Data storage
│   ├── transcripts/         # Podcast transcripts
│   ├── research/            # Research findings
│   ├── content/             # Generated and published content
│   └── memory/              # Agent memory and learning
├── utils/                   # Utility modules
│   ├── api_client.py        # API client wrappers
│   ├── file_manager.py      # File operations
│   └── logger.py            # Logging utilities
├── main.py                  # Main application runner
└── requirements.txt         # Python dependencies
```

## ⚙️ Configuration

### System Settings (`config/settings.json`)
```json
{
  "publishing": {
    "posts_per_day": 3,
    "optimal_times": ["09:00", "14:00", "18:00"],
    "timezone": "Australia/Perth"
  },
  "content": {
    "max_content_per_episode": 15,
    "content_mix": {
      "threads": 0.4,
      "single_tweets": 0.6
    }
  }
}
```

### Brand Voice (`data/memory/brand_voice.json`)
Defines Pete & Andy's contrarian, framework-driven style with specific patterns and preferences.

## 🔄 Workflow

1. **Transcript Input**: Upload podcast transcript to `data/transcripts/`
2. **Insight Extraction**: CMO agent identifies key business frameworks
3. **Research Phase**: Research agent finds supporting evidence and case studies
4. **Content Generation**: Content agent creates multiple social media pieces
5. **Quality Validation**: Brand voice and quality checks ensure consistency
6. **Publishing**: Publishing agent schedules content via Typefully
7. **Learning**: System updates memory based on performance

## 📊 Content Types Generated

### Framework Threads (5-7 tweets)
- Break down business concepts into actionable steps
- Include supporting data and case studies
- Contrarian hooks that challenge conventional wisdom

### Single Tweets
- Contrarian takes on business advice
- Case study highlights
- Tactical tips for SME owners

### Quote Tweets
- Data-backed challenges to conventional wisdom
- Specific statistics and examples

## 🛠️ Usage Examples

### Process Single Episode
```bash
python main.py data/transcripts/episode_047.txt
```

### Check System Status
```bash
python main.py --status
```

### View Generated Content
```bash
# Check latest generated content
ls -la data/content/generated/
cat data/content/generated/latest_content.json
```

### Monitor System Health
```bash
# View agent logs
tail -f logs/cmo_orchestrator.log
```

## 📈 Performance Metrics

The system tracks:
- Episodes processed
- Insights extracted per episode
- Content pieces generated
- Publishing success rate
- Content quality scores
- Brand voice consistency

## 💰 Cost Management & Bill Shock Protection

### OpenRouter Integration (90% Cost Savings) 🚀
The system uses intelligent model routing for dramatic cost reduction:

- **Claude**: Reserved for complex reasoning (insight extraction, prioritization)
- **DeepSeek via OpenRouter**: Handles content generation tasks at ~1/50th the cost
- **Automatic Routing**: Tasks routed to optimal model automatically
- **Quality Maintained**: Strategic tasks still use Claude's superior reasoning

### Built-in Cost Protection
The system includes comprehensive cost monitoring to prevent unexpected API bills:

- **Daily Token Limits**: 50,000 tokens/day (≈ $2-4/day with OpenRouter)
- **Episode Limits**: 25,000 tokens/episode (≈ $0.50-1.50/episode with OpenRouter)
- **Monthly Budget**: $20/month default with OpenRouter
- **Pre-request Validation**: Blocks requests that would exceed limits

### Cost Monitoring Commands
```bash
# Show OpenRouter cost savings comparison
python main.py --cost-comparison

# View current usage and costs
python main.py --cost-report

# Check cost breakdown for specific episode
python scripts/cost_report.py --episode episode_001

# View system status including cost info
python main.py --status
```

### Cost Configuration
Edit `config/settings.json` to adjust limits:
```json
{
  "cost_limits": {
    "daily_token_limit": 30000,
    "episode_token_limit": 15000,
    "monthly_budget_usd": 50,
    "enable_cost_monitoring": true
  }
}
```

### Expected Costs
**With OpenRouter (Recommended):**
- **Per Episode**: $0.50-1.50 (25k tokens, 90% via DeepSeek)
- **Daily Usage**: $2-4 maximum with limits
- **Monthly**: $5-15 for 1 episode/week

**Claude-Only (Legacy):**
- **Per Episode**: $3-6 (15k tokens)
- **Daily Usage**: $6-12 maximum
- **Monthly**: $20-50 for 1 episode/week

## 🔧 Troubleshooting

### Common Issues

**Cost Limit Exceeded**
```bash
# Check current usage
python main.py --cost-report

# Adjust limits in config/settings.json
# Or wait for daily/monthly reset
```

**Claude API Authentication Failed**
```bash
# Verify API key is set
python -c "import os; from dotenv import load_dotenv; load_dotenv('config/api_keys.env'); print('Claude API Key:', bool(os.getenv('CLAUDE_API_KEY')))"
```

**No Content Generated**
- Check transcript quality and length (minimum 100 characters)
- Verify Claude API is responding
- Review logs in `logs/cmo_orchestrator.log`

**Publishing Fails**
- Verify Typefully API key
- Check rate limits (free tier: 30 requests/hour)
- Review publishing agent logs

### Health Check
```bash
python main.py --status
```

## 🚀 Scaling & Advanced Usage

### Multiple Podcasts
- Create separate brand voice configurations
- Use episode-specific settings
- Maintain separate memory for each show

### Custom Content Types
- Extend content agent with new templates
- Add platform-specific formatting
- Implement custom validation rules

### Performance Optimization
- Adjust content mix based on engagement
- Optimize posting times for audience
- Refine brand voice based on successful content

## 📝 Development

### Adding New Features
1. Extend base agent classes
2. Update prompt templates
3. Add configuration options
4. Test with sample data

### Testing
```bash
# Test with sample transcript
python main.py data/transcripts/test_episode.txt

# Check generated content
python -c "import json; print(json.dumps(json.load(open('data/content/generated/latest.json')), indent=2))"
```

## 📄 License

This project is built for "The Good Stuff" podcast. See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## 📞 Support

For issues and questions:
1. Check system logs in `logs/` directory
2. Run `python main.py --status` for health check
3. Review this README for troubleshooting
4. Create GitHub issue with logs and error details

---

*Built with Claude Code for autonomous podcast content marketing.*