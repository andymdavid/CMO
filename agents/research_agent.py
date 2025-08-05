import json
from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from config.prompts.research_prompts import (
    RESEARCH_SYSTEM_PROMPT, 
    SEARCH_QUERY_GENERATION_PROMPT, 
    RESEARCH_ANALYSIS_PROMPT
)
from utils.api_client import OpenRouterClient, ModelRouter, WebSearchClient, ContentGenerationError


class ResearchAgent(BaseAgent):
    """
    Research agent that finds supporting evidence, case studies, and data
    to strengthen business insights for social media content.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("research_agent", config)
        
        # Initialize OpenRouter client and model router
        openrouter_key = config.get("openrouter_api_key")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY is required for research operations")
        
        self.openrouter_client = OpenRouterClient(openrouter_key, config)
        self.model_router = ModelRouter(self.openrouter_client)
        self.web_search_client = WebSearchClient()
        
        # Configuration
        self.max_searches_per_insight = config.get("research", {}).get("max_searches_per_insight", 3)
        self.credibility_threshold = config.get("research", {}).get("source_credibility_threshold", 0.7)
        self.recency_preference_days = config.get("research", {}).get("recency_preference_days", 730)
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process research task and return structured findings"""
        if not self.validate_input(task):
            raise ValueError("Invalid research task format")
        
        task_type = task.get("type", "research_insight")
        
        if task_type == "research_insight":
            return self.research_business_insight(task)
        else:
            raise ValueError(f"Unsupported research task type: {task_type}")
    
    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate research task input"""
        required_fields = ["insight", "research_angle"]
        return all(field in task for field in required_fields)
    
    def research_business_insight(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Research a business insight and find supporting evidence"""
        insight = task["insight"]
        research_angle = task["research_angle"]
        max_sources = task.get("max_sources", 3)
        
        self.log_decision("research_started", 
                         {"insight_id": insight["id"], "research_angle": research_angle}, 
                         "beginning_research_process")
        
        try:
            # Generate targeted search queries
            search_queries = self.generate_search_queries(insight, research_angle)
            
            # Execute searches and gather results
            all_search_results = []
            for query_data in search_queries[:self.max_searches_per_insight]:
                search_results = self.execute_web_search(query_data["query"])
                all_search_results.extend(search_results)
            
            # Analyze and filter results
            research_analysis = self.analyze_search_results(insight, all_search_results)
            
            # Package research findings
            research_package = self.package_research_findings(insight, research_analysis, max_sources)
            
            # Save research data
            research_file = self.file_manager.save_research_data(insight["id"], research_package)
            
            self.log_decision("research_completed", 
                            {"insight_id": insight["id"], 
                             "findings_count": len(research_package.get("key_findings", [])),
                             "case_studies_count": len(research_package.get("case_studies", []))}, 
                            "research_package_created")
            
            # Update performance metrics
            self.update_performance_metrics("insights_researched", 
                                          self.memory.get("performance_metrics", {}).get("insights_researched", 0) + 1)
            
            # Learn from successful research patterns
            if len(research_package.get("key_findings", [])) >= 2:
                self.learn_from_success({
                    "research_angle": research_angle,
                    "insight_type": insight.get("type"),
                    "query_patterns": [q["query"] for q in search_queries],
                    "findings_count": len(research_package.get("key_findings", []))
                })
            
            self.save_memory()
            
            return research_package
            
        except Exception as e:
            self.log_decision("research_failed", 
                            {"insight_id": insight["id"], "error": str(e)}, 
                            "research_process_failed")
            
            # Learn from failure
            self.learn_from_failure({
                "research_angle": research_angle,
                "insight_type": insight.get("type"),
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            
            # Return minimal research package on failure
            return {
                "insight_id": insight["id"],
                "research_status": "failed",
                "error": str(e),
                "key_findings": [],
                "case_studies": [],
                "supporting_data": []
            }
    
    def generate_search_queries(self, insight: Dict[str, Any], research_angle: str) -> List[Dict[str, Any]]:
        """Generate targeted search queries for the business insight"""
        try:
            prompt = SEARCH_QUERY_GENERATION_PROMPT.format(
                insight_title=insight["title"],
                business_context=insight.get("business_context", ""),
                key_terms=", ".join(insight.get("key_terms", [])),
                research_angle=research_angle
            )
            
            response = self.model_router.generate_content(
                task_type="search_query_generation",
                system_prompt=RESEARCH_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=1000,
                agent_name="research_agent"
            )
            
            # Parse query generation response
            try:
                queries = json.loads(response)
                if not isinstance(queries, list):
                    raise ValueError("Response is not a list")
            except json.JSONDecodeError:
                # Fallback to manual query generation
                queries = self._generate_fallback_queries(insight, research_angle)
            
            self.log_decision("queries_generated", 
                            {"insight_id": insight["id"], "query_count": len(queries)}, 
                            "search_queries_ready")
            
            return queries
            
        except Exception as e:
            self.logger.log_error("query_generation_error", str(e))
            return self._generate_fallback_queries(insight, research_angle)
    
    def execute_web_search(self, query: str) -> List[Dict[str, Any]]:
        """Execute web search and return results"""
        try:
            # In Claude Code environment, this will use actual web search
            search_results = self.web_search_client.search(query, max_results=5)
            
            self.log_decision("web_search_executed", 
                            {"query": query, "results_count": len(search_results)}, 
                            "search_completed")
            
            return search_results
            
        except Exception as e:
            self.logger.log_error("web_search_error", str(e), {"query": query})
            return []
    
    def analyze_search_results(self, insight: Dict[str, Any], search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze search results for relevance and credibility"""
        if not search_results:
            return {
                "analysis_summary": "No search results found for analysis",
                "key_findings": [],
                "case_studies": [],
                "supporting_data": []
            }
        
        try:
            # Use Claude to analyze search results
            prompt = RESEARCH_ANALYSIS_PROMPT.format(
                insight_title=insight["title"],
                search_results=json.dumps(search_results[:10], indent=2)  # Limit to first 10 results
            )
            
            response = self.model_router.generate_content(
                task_type="research_analysis",
                system_prompt=RESEARCH_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=2000,
                agent_name="research_agent"
            )
            
            # Parse analysis response
            try:
                analysis = json.loads(response)
            except json.JSONDecodeError:
                # Fallback analysis
                analysis = self._generate_fallback_analysis(search_results)
            
            self.log_decision("results_analyzed", 
                            {"insight_id": insight["id"], 
                             "findings": len(analysis.get("key_findings", [])),
                             "case_studies": len(analysis.get("case_studies", []))}, 
                            "analysis_completed")
            
            return analysis
            
        except Exception as e:
            self.logger.log_error("analysis_error", str(e))
            return self._generate_fallback_analysis(search_results)
    
    def package_research_findings(self, insight: Dict[str, Any], analysis: Dict[str, Any], max_sources: int) -> Dict[str, Any]:
        """Package research findings for content agent consumption"""
        # Filter findings by credibility threshold
        high_quality_findings = [
            finding for finding in analysis.get("key_findings", [])
            if finding.get("credibility_score", 0) >= self.credibility_threshold
        ][:max_sources]
        
        high_quality_case_studies = [
            case_study for case_study in analysis.get("case_studies", [])
            if case_study.get("credibility_score", 0) >= self.credibility_threshold
        ][:max_sources]
        
        high_quality_data = [
            data for data in analysis.get("supporting_data", [])
            if data.get("credibility_score", 0) >= self.credibility_threshold
        ][:max_sources]
        
        research_package = {
            "insight_id": insight["id"],
            "research_summary": analysis.get("analysis_summary", ""),
            "research_quality_score": self._calculate_research_quality_score(
                high_quality_findings, high_quality_case_studies, high_quality_data
            ),
            "key_findings": high_quality_findings,
            "case_studies": high_quality_case_studies,
            "supporting_data": high_quality_data,
            "research_metadata": {
                "sources_found": len(analysis.get("key_findings", [])),
                "sources_filtered": len(high_quality_findings),
                "credibility_threshold": self.credibility_threshold,
                "research_completed_at": self.file_manager.load_memory("research_agent").get("last_updated")
            }
        }
        
        return research_package
    
    def _generate_fallback_queries(self, insight: Dict[str, Any], research_angle: str) -> List[Dict[str, Any]]:
        """Generate fallback queries when Claude query generation fails"""
        framework_terms = insight.get("key_terms", [insight["title"]])
        
        base_queries = [
            f"SME {framework_terms[0]} case study success",
            f"small business {framework_terms[0]} examples Australia",
            f"{framework_terms[0]} implementation results data"
        ]
        
        # Add research angle specific queries
        if research_angle == "supporting_evidence":
            base_queries.append(f"{framework_terms[0]} benefits statistics SME")
        elif research_angle == "contrarian_examples":
            base_queries.append(f"{framework_terms[0]} failure risks small business")
        
        return [
            {
                "query": query,
                "purpose": "fallback_search",
                "expected_sources": ["business_publications"]
            }
            for query in base_queries
        ]
    
    def _generate_fallback_analysis(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate fallback analysis when Claude analysis fails"""
        # Simple heuristic-based analysis
        findings = []
        for i, result in enumerate(search_results[:3]):
            findings.append({
                "finding": f"Information from {result.get('source', 'source')}",
                "source": result.get("source", "unknown"),
                "credibility_score": result.get("credibility_score", 0.5),
                "relevance_score": result.get("relevance_score", 0.5),
                "content_application": "General supporting information"
            })
        
        return {
            "analysis_summary": "Fallback analysis of search results",
            "key_findings": findings,
            "case_studies": [],
            "supporting_data": []
        }
    
    def _calculate_research_quality_score(self, findings: List, case_studies: List, data: List) -> float:
        """Calculate overall research quality score"""
        total_items = len(findings) + len(case_studies) + len(data)
        if total_items == 0:
            return 0.0
        
        # Weight different types of research
        findings_score = sum(f.get("credibility_score", 0) for f in findings) * 0.4
        case_studies_score = sum(c.get("credibility_score", 0) for c in case_studies) * 0.4
        data_score = sum(d.get("credibility_score", 0) for d in data) * 0.2
        
        return min((findings_score + case_studies_score + data_score) / max(total_items, 1), 1.0)