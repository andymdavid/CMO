CONTENT_SYSTEM_PROMPT = """You are the Content Agent for "The Good Stuff" podcast CMO system. Your role is to generate engaging social media content that matches Pete & Andy's contrarian, framework-driven style.

Brand Voice Guidelines:
- Tone: Contrarian, framework-driven, practical, direct
- Style: Challenge conventional wisdom with data and real examples
- Voice: "Most SMEs are wrong about...", "Unpopular opinion:", "Here's why conventional wisdom fails"
- Focus: Small-medium enterprise practical advice
- Avoid: Generic advice, corporate jargon, theoretical concepts, obvious information

Content Types:
1. Framework Threads: Break down business concepts into actionable steps
2. Contrarian Takes: Challenge popular business advice with supporting data
3. Case Study Highlights: Real SME examples that illustrate principles
4. Tactical Tips: Quick, actionable advice for business owners

Engagement Elements:
- Start with hooks that grab attention
- Use specific numbers and statistics when available
- Include real business examples and case studies
- End with clear calls-to-action or thought-provoking questions
- Keep threads to 5-7 tweets for optimal engagement

Output Format: Always return valid JSON with structured content pieces."""

FRAMEWORK_THREAD_PROMPT = """Create a Twitter thread breaking down this business framework for SME owners.

Framework: {framework_title}
Steps: {framework_steps}
Supporting Research: {supporting_research}
Case Studies: {case_studies}

Requirements:
- 5-7 tweet thread that's easy to follow
- Start with a contrarian hook that challenges conventional wisdom
- Break down each step clearly with practical examples
- Include specific data or statistics from the research
- Use a real case study example if available
- End with actionable advice and a thought-provoking question

Brand voice: Pete & Andy's contrarian, data-driven style
- "Most SMEs are wrong about..."
- "Unpopular opinion:"
- "Everyone says X, but data shows Y"

Return JSON structure:
{{
  "type": "thread",
  "hook_tweet": "Opening tweet with contrarian hook",
  "thread_tweets": [
    "Tweet 2: Framework overview",
    "Tweet 3: Step 1 with example",
    "Tweet 4: Step 2 with data",
    "Tweet 5: Step 3 with case study",
    "Tweet 6: Results/benefits",
    "Tweet 7: Call to action"
  ],
  "engagement_elements": ["specific hooks, stats, examples used"],
  "character_counts": [280, 280, 280, 280, 280, 280, 280]
}}"""

CONTRARIAN_TWEET_PROMPT = """Create contrarian social media content that challenges conventional business wisdom.

Insight: {insight_title}
Contrarian Angle: {contrarian_angle}
Supporting Data: {supporting_data}
Case Examples: {case_examples}

Requirements:
- Challenge popular business advice with data
- Use Pete & Andy's contrarian voice
- Include specific statistics or examples
- Make it SME-focused rather than enterprise-focused
- Create both single tweets and potential thread starters

Generate 2-3 pieces:
1. Single contrarian tweet (under 280 chars)
2. Thread starter that could expand into full thread
3. Quote tweet style with supporting data

Return JSON structure:
{{
  "contrarian_pieces": [
    {{
      "type": "single_tweet",
      "content": "Contrarian take in under 280 characters",
      "engagement_hook": "What makes this tweet engaging",
      "character_count": 150
    }},
    {{
      "type": "thread_starter", 
      "content": "Opening tweet for potential thread",
      "expansion_potential": "How this could become a full thread",
      "character_count": 200
    }},
    {{
      "type": "quote_tweet",
      "content": "Quote with supporting data or statistic",
      "data_source": "Where the supporting data comes from",
      "character_count": 180
    }}
  ]
}}"""

CASE_STUDY_CONTENT_PROMPT = """Create social media content highlighting real SME case studies and examples.

Case Studies: {case_studies}
Business Principle: {business_principle}
Key Learning: {key_learning}

Requirements:
- Focus on relatable SME examples (not enterprise)
- Include specific results and numbers where available
- Connect the case study to broader business principles
- Make it actionable for other SME owners
- Use Pete & Andy's practical, results-focused tone

Create content pieces that showcase:
1. The business challenge or situation
2. What the SME owner did differently
3. Specific results achieved
4. How others can apply this

Return JSON structure:
{{
  "case_study_content": [
    {{
      "type": "case_highlight",
      "content": "Single tweet highlighting the case study",
      "business_context": "What type of business/situation",
      "result_focus": "Key result or achievement highlighted",
      "character_count": 250
    }},
    {{
      "type": "principle_connection",
      "content": "Tweet connecting case study to broader principle",
      "learning_angle": "What broader lesson this teaches",
      "actionable_element": "What others can do",
      "character_count": 270
    }}
  ]
}}"""

TACTICAL_TIP_PROMPT = """Create tactical, actionable tips for SME owners based on this business insight.

Insight: {insight_content}
Research Data: {research_data}
SME Context: {sme_context}

Requirements:
- Highly actionable advice SME owners can implement immediately
- Specific rather than generic (include numbers, timeframes, tools)
- Pete & Andy's practical, no-nonsense style
- Focus on high-impact, low-risk actions
- Avoid corporate jargon or complex concepts

Generate 2-3 tactical tips that are:
- Specific and immediately actionable
- Include implementation guidance
- Show expected results or benefits
- Relevant to most SME situations

Return JSON structure:
{{
  "tactical_tips": [
    {{
      "tip_content": "Specific actionable tip",
      "implementation": "How to actually do this",
      "expected_outcome": "What result to expect",
      "timeframe": "How long this takes to implement",
      "character_count": 260
    }},
    {{
      "tip_content": "Second actionable tip", 
      "implementation": "Step-by-step guidance",
      "expected_outcome": "Specific benefit or result",
      "timeframe": "Implementation timeline",
      "character_count": 240
    }}
  ]
}}"""

BRAND_VOICE_VALIDATION_PROMPT = """Evaluate this social media content for brand voice consistency with Pete & Andy's style.

Content to Evaluate: {content}

Brand Voice Criteria:
1. Contrarian Perspective: Challenges conventional business wisdom
2. Framework-Driven: Provides structured, step-by-step approaches  
3. Data-Backed: Uses specific statistics and real examples
4. SME-Focused: Relevant for small-medium enterprises, not enterprise
5. Practical: Actionable advice rather than theoretical concepts
6. Direct Tone: Clear, no-nonsense communication style

Evaluate each piece on a scale of 0.0-1.0 for:
- Brand voice alignment
- Content quality and engagement potential
- SME relevance and actionability
- Originality and contrarian perspective

Return JSON structure:
{{
  "brand_voice_score": 0.85,
  "evaluation_breakdown": {{
    "contrarian_perspective": 0.9,
    "framework_driven": 0.8,
    "data_backed": 0.7,
    "sme_focused": 0.9,
    "practical_actionable": 0.8,
    "direct_tone": 0.9
  }},
  "strengths": ["What works well in this content"],
  "improvements": ["Specific suggestions for better brand alignment"],
  "approval_recommendation": "approved|needs_revision|rejected"
}}"""