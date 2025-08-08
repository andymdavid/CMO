import json
from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from config.prompts.cmo_prompts import CMO_SYSTEM_PROMPT, INSIGHT_EXTRACTION_PROMPT, INSIGHT_PRIORITIZATION_PROMPT
from utils.api_client import OpenRouterClient, ModelRouter, ContentGenerationError


class CMOOrchestrator(BaseAgent):
    """
    Main orchestrator agent that processes podcast transcripts and coordinates
    content creation across all specialist agents.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("cmo_orchestrator", config)
        # Initialize OpenRouter client and model router
        openrouter_key = config.get("openrouter_api_key")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY is required for CMO operation")
        
        self.openrouter_client = OpenRouterClient(openrouter_key, config)
        self.model_router = ModelRouter(self.openrouter_client)
        
        # Will be injected during initialization
        self.research_agent = None
        self.content_agent = None  
        self.publishing_agent = None
        
        # Configuration with cost limits
        self.max_insights_per_episode = min(
            config.get("content", {}).get("max_content_per_episode", 8),
            config.get("cost_limits", {}).get("max_insights_per_episode", 5)
        )
        self.min_priority_score = 0.6  # Minimum score for content creation
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a general task - delegates to process_transcript for transcript tasks"""
        if not self.validate_input(task):
            raise ValueError("Invalid task format")
        
        task_type = task.get("type", "transcript_processing")
        
        if task_type == "transcript_processing":
            return self.process_transcript(task["transcript_path"])
        else:
            raise ValueError(f"Unsupported task type: {task_type}")
    
    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate task input"""
        required_fields = ["type", "transcript_path"] if task.get("type") == "transcript_processing" else ["transcript_path"]
        return all(field in task for field in required_fields)
    
    def process_transcript(self, transcript_path: str) -> Dict[str, Any]:
        """
        Main workflow: Process transcript and coordinate content creation
        """
        self.log_decision("transcript_processing", {"file": transcript_path}, "started")
        
        try:
            # Load and validate transcript
            transcript_data = self.file_manager.load_transcript(transcript_path)
            episode_id = self.file_manager.get_episode_id_from_transcript(transcript_path)
            self._current_episode_id = episode_id  # Store for cost tracking
            
            self.log_decision("transcript_loaded", 
                            {"episode_id": episode_id, "word_count": transcript_data["word_count"]}, 
                            "success")
            
            # Extract business insights
            insights = self.extract_business_insights(transcript_data["content"])
            
            # Prioritize insights for content creation
            prioritized_insights = self.prioritize_insights(insights)
            
            # Filter by minimum priority score and limit count
            qualified_insights = [
                insight for insight in prioritized_insights 
                if insight.get("priority_score", 0) >= self.min_priority_score
            ][:self.max_insights_per_episode]
            
            self.log_decision("insights_filtered", 
                            {"total_extracted": len(insights), 
                             "qualified": len(qualified_insights)}, 
                            "ready_for_content_creation")
            
            # Coordinate content creation with specialist agents
            results = self.coordinate_content_creation(episode_id, qualified_insights)
            
            # Save processing results
            processing_summary = {
                "episode_id": episode_id,
                "transcript_data": transcript_data,
                "insights_extracted": len(insights),
                "insights_processed": len(qualified_insights),
                "content_pipeline_results": results,
                "processing_completed_at": self.file_manager.load_memory("cmo_orchestrator").get("last_updated")
            }
            
            self.file_manager.save_generated_content(episode_id, processing_summary)
            
            self.log_decision("transcript_processing", 
                            {"episode_id": episode_id, "insights_count": len(qualified_insights)}, 
                            "completed")
            
            # Update performance metrics
            self.update_performance_metrics("episodes_processed", 
                                          self.memory.get("performance_metrics", {}).get("episodes_processed", 0) + 1)
            self.update_performance_metrics("avg_insights_per_episode", 
                                          len(qualified_insights))
            
            # Save updated memory
            self.save_memory()
            
            return processing_summary
            
        except Exception as e:
            self.log_decision("transcript_processing", 
                            {"file": transcript_path, "error": str(e)}, 
                            "failed")
            raise
    
    def extract_business_insights(self, transcript: str) -> List[Dict[str, Any]]:
        """Use Claude to extract key business frameworks and insights"""
        try:
            prompt = INSIGHT_EXTRACTION_PROMPT.format(transcript=transcript)
            
            response = self.model_router.generate_content(
                task_type="insight_extraction",
                system_prompt=CMO_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=2000,
                agent_name="cmo_orchestrator",
                episode_id=getattr(self, '_current_episode_id', None)
            )
            
            # Parse structured response from Claude
            # First, clean the response by removing markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response.replace('```', '').strip()
            
            try:
                parsed_response = json.loads(cleaned_response)
                
                # Handle different response formats from Claude
                if isinstance(parsed_response, list):
                    insights = parsed_response
                elif isinstance(parsed_response, dict) and 'insights' in parsed_response:
                    insights = parsed_response['insights']
                else:
                    self.logger.log_error("unexpected_response_format", 
                                        f"Unexpected response format: {type(parsed_response).__name__}", 
                                        {"response_content": str(parsed_response)[:500]})
                    raise ValueError("Response format not recognized - expected list or dict with 'insights' key")
                
                if not isinstance(insights, list):
                    raise ValueError("Insights is not a list")
                    
            except json.JSONDecodeError as e:
                self.logger.log_error("json_parse_error", f"Failed to parse Claude response: {e}", {"response": cleaned_response[:500]})
                # Try to extract JSON from response if it's wrapped in other text
                import re
                json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
                if json_match:
                    try:
                        insights = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        raise ContentGenerationError("Could not extract valid JSON from Claude response")
                else:
                    raise ContentGenerationError("Could not extract valid JSON from Claude response")
            
            # Validate insight structure
            validated_insights = []
            for i, insight in enumerate(insights):
                if self._validate_insight_structure(insight):
                    insight["id"] = f"insight_{i+1}_{insight.get('id', str(i+1))}"
                    validated_insights.append(insight)
                else:
                    self.logger.log_error("invalid_insight_structure", 
                                        f"Skipping insight {i} due to invalid structure", 
                                        {"insight": insight})
            
            self.log_decision("insight_extraction", 
                            {"transcript_length": len(transcript), "insights_found": len(validated_insights)}, 
                            f"extracted {len(validated_insights)} valid insights")
            
            return validated_insights
            
        except ContentGenerationError:
            raise
        except Exception as e:
            self.logger.log_error("insight_extraction_error", str(e))
            raise ContentGenerationError(f"Failed to extract insights: {e}")
    
    def prioritize_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank insights by content potential and brand alignment"""
        if not insights:
            return []
        
        try:
            # Use Claude to prioritize insights
            prompt = INSIGHT_PRIORITIZATION_PROMPT.format(insights=json.dumps(insights, indent=2))
            
            response = self.model_router.generate_content(
                task_type="insight_prioritization",
                system_prompt=CMO_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=2000,
                agent_name="cmo_orchestrator",
                episode_id=getattr(self, '_current_episode_id', None)
            )
            
            # Parse prioritized insights
            try:
                # Clean the response by removing markdown code blocks if present
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
                elif cleaned_response.startswith('```'):
                    cleaned_response = cleaned_response.replace('```', '').strip()
                
                parsed_response = json.loads(cleaned_response)
                
                # Handle different response formats from Claude
                if isinstance(parsed_response, list):
                    prioritized_insights = parsed_response
                elif isinstance(parsed_response, dict) and 'insights' in parsed_response:
                    prioritized_insights = parsed_response['insights']
                else:
                    # Try to get any array from the response
                    for value in parsed_response.values():
                        if isinstance(value, list):
                            prioritized_insights = value
                            break
                    else:
                        raise ValueError("No valid insights array found in response")
            except json.JSONDecodeError:
                # Fallback to manual prioritization if Claude response is invalid
                self.logger.log_error("prioritization_parse_error", 
                                    "Failed to parse prioritization response, using fallback")
                prioritized_insights = self._fallback_prioritization(insights)
            
            self.log_decision("insight_prioritization", 
                            {"total_insights": len(insights)}, 
                            f"prioritized {len(prioritized_insights)} insights")
            
            return prioritized_insights
            
        except Exception as e:
            self.logger.log_error("prioritization_error", str(e))
            # Use fallback prioritization
            return self._fallback_prioritization(insights)
    
    def coordinate_content_creation(self, episode_id: str, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Coordinate research, content generation, and publishing for all insights"""
        if not all([self.research_agent, self.content_agent, self.publishing_agent]):
            raise ValueError("Specialist agents not properly initialized")
        
        content_pipeline_results = []
        
        for insight in insights:
            try:
                self.log_decision("processing_insight", 
                                {"insight_id": insight["id"], "title": insight["title"]}, 
                                "started")
                
                # Research phase
                research_task = self._create_research_task(insight)
                research_results = self.research_agent.process_task(research_task)
                
                # Content generation phase
                content_task = self._create_content_task(insight, research_results)
                content_results = self.content_agent.process_task(content_task)
                
                # Publishing phase
                publishing_task = self._create_publishing_task(episode_id, content_results)
                publishing_results = self.publishing_agent.process_task(publishing_task)
                
                pipeline_result = {
                    "insight": insight,
                    "research": research_results,
                    "content": content_results,
                    "publishing": publishing_results,
                    "status": "completed"
                }
                
                content_pipeline_results.append(pipeline_result)
                
                self.log_decision("processing_insight", 
                                {"insight_id": insight["id"]}, 
                                "completed_successfully")
                
            except Exception as e:
                self.logger.log_error("insight_processing_error", 
                                    str(e), 
                                    {"insight_id": insight["id"], "title": insight["title"]})
                
                # Add failed result to maintain tracking
                content_pipeline_results.append({
                    "insight": insight,
                    "error": str(e),
                    "status": "failed"
                })
        
        return content_pipeline_results
    
    def _create_research_task(self, insight: Dict[str, Any]) -> Dict[str, Any]:
        """Create research task for the research agent"""
        return {
            "type": "research_insight",
            "insight": insight,
            "research_angle": self._determine_research_angle(insight),
            "max_sources": 3,
            "focus_areas": ["sme_examples", "supporting_data", "case_studies"]
        }
    
    def _create_content_task(self, insight: Dict[str, Any], research_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create content generation task for the content agent"""
        return {
            "type": "generate_content",
            "insight": insight,
            "research_data": research_results,
            "content_requirements": {
                "brand_voice": self.file_manager.load_brand_voice(),
                "max_pieces": 5,
                "content_mix": self.config.get("content", {}).get("content_mix", {})
            }
        }
    
    def _create_publishing_task(self, episode_id: str, content_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create publishing task for the publishing agent"""
        return {
            "type": "schedule_content",
            "episode_id": episode_id,
            "content_pieces": content_results.get("content_pieces", []),
            "publishing_config": self.config.get("publishing", {})
        }
    
    def _determine_research_angle(self, insight: Dict[str, Any]) -> str:
        """Determine the best research angle for an insight"""
        insight_type = insight.get("type", "")
        
        if insight_type == "contrarian_take":
            return "supporting_evidence"
        elif insight_type == "framework":
            return "implementation_examples"
        elif insight_type == "case_study":
            return "similar_cases"
        else:
            return "general_research"
    
    def _validate_insight_structure(self, insight: Dict[str, Any]) -> bool:
        """Validate that an insight has the required structure"""
        required_fields = ["title", "type", "content"]
        optional_fields = ["key_terms", "business_context", "steps", "contrarian_angle"]
        
        # Check required fields
        if not all(field in insight for field in required_fields):
            return False
        
        # Validate insight type
        valid_types = ["framework", "contrarian_take", "case_study", "tactical_tip"]
        if insight.get("type") not in valid_types:
            return False
        
        return True
    
    def _fallback_prioritization(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback prioritization using simple scoring"""
        scoring_criteria = {
            "framework_clarity": 0.3,
            "contrarian_potential": 0.25,
            "sme_relevance": 0.25,
            "content_variety": 0.2
        }
        
        for insight in insights:
            # Simple scoring based on available data
            score = 0.5  # Base score
            
            if insight.get("type") == "framework":
                score += 0.2
            if insight.get("contrarian_angle"):
                score += 0.2
            if len(insight.get("key_terms", [])) >= 3:
                score += 0.1
            
            insight["priority_score"] = min(score, 1.0)
        
        # Sort by priority score, highest first
        return sorted(insights, key=lambda x: x.get("priority_score", 0), reverse=True)