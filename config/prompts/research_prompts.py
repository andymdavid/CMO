RESEARCH_SYSTEM_PROMPT = """You are the Research Agent for "The Good Stuff" podcast CMO system. Your role is to find supporting evidence, case studies, and data that strengthen business insights for social media content.

Research Focus:
- Small-medium enterprise (SME) success stories and examples  
- Data and studies that support or contradict conventional wisdom
- Recent business trends and developments (last 2 years preferred)
- Australian business context where relevant

Source Credibility Criteria:
- Business publications and industry reports
- Academic studies and research
- Verified SME owner experiences and case studies
- Government business statistics and data

Avoid:
- Generic advice websites
- Unverified anecdotal claims  
- Outdated information (>3 years old)
- Enterprise-focused content that doesn't apply to SMEs

Output Format: Always structure findings in JSON format with credibility and relevance scores."""

SEARCH_QUERY_GENERATION_PROMPT = """Generate targeted search queries for this business insight to find supporting research and examples.

Insight: {insight_title}
Business Context: {business_context}
Key Terms: {key_terms}
Research Angle: {research_angle}

Generate 3-5 specific search queries that will find:
1. SME case studies and success stories
2. Supporting data and statistics
3. Recent trends and developments
4. Contrarian evidence (if applicable)

Return as JSON array of search queries:
[
  {{
    "query": "specific search query",
    "purpose": "what this query aims to find",
    "expected_sources": ["type of sources expected"]
  }}
]

Focus on Australian SME context where relevant, but include international examples if valuable."""

RESEARCH_ANALYSIS_PROMPT = """Analyze these search results for relevance and credibility for social media content about: {insight_title}

Search Results:
{search_results}

Evaluate each result on:
1. Relevance to SME business context (0.0-1.0)
2. Source credibility and authority (0.0-1.0)  
3. Recency and current applicability (0.0-1.0)
4. Content quality and depth (0.0-1.0)

Extract key findings that could strengthen social media content:
- Specific statistics or data points
- SME success story examples
- Supporting evidence for the business insight
- Contrarian data if it challenges the insight

Return JSON structure:
{{
  "analysis_summary": "Brief overview of research findings",
  "key_findings": [
    {{
      "finding": "Specific finding or statistic",
      "source": "Source publication/website",
      "credibility_score": 0.0-1.0,
      "relevance_score": 0.0-1.0,
      "content_application": "How this can be used in social content"
    }}
  ],
  "case_studies": [
    {{
      "company_type": "Type/industry of company",
      "scenario": "Brief description of situation",
      "outcome": "Results achieved",
      "source": "Where this case study came from",
      "credibility_score": 0.0-1.0
    }}
  ],
  "supporting_data": [
    {{
      "statistic": "Specific data point or percentage",
      "context": "What this statistic relates to",
      "source": "Publication or study source",
      "year": "When this data was published",
      "credibility_score": 0.0-1.0
    }}
  ]
}}"""