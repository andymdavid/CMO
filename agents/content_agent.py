import json
from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from config.prompts.content_prompts import (
    CONTENT_SYSTEM_PROMPT,
    FRAMEWORK_THREAD_PROMPT,
    CONTRARIAN_TWEET_PROMPT, 
    CASE_STUDY_CONTENT_PROMPT,
    TACTICAL_TIP_PROMPT,
    BRAND_VOICE_VALIDATION_PROMPT
)
from utils.api_client import OpenRouterClient, ModelRouter, ContentGenerationError


class ContentAgent(BaseAgent):
    """
    Content agent that generates social media content from business insights and research data,
    maintaining consistent brand voice and quality standards.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("content_agent", config)
        
        # Initialize OpenRouter client and model router
        openrouter_key = config.get("openrouter_api_key")
        if not openrouter_key:
            raise ValueError("OPENROUTER_API_KEY is required for content generation")
        
        self.openrouter_client = OpenRouterClient(openrouter_key, config)
        self.model_router = ModelRouter(self.openrouter_client)
        self.logger.log_info("Content agent initialized with OpenRouter - all models via unified API")
        
        # Load brand voice and content templates
        self.brand_voice = self.file_manager.load_brand_voice()
        
        # Configuration
        self.max_tweet_length = config.get("content", {}).get("max_tweet_length", 280)
        self.content_mix = config.get("content", {}).get("content_mix", {})
        self.thread_length_range = config.get("content", {}).get("thread_length_range", [5, 7])
        self.quality_threshold = 0.7  # Minimum quality score for approval
        self.brand_voice_threshold = 0.8  # Minimum brand voice score
    
    def _clean_json_response(self, response: str) -> str:
        """Clean Claude's response by removing markdown code blocks"""
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
        elif cleaned_response.startswith('```'):
            cleaned_response = cleaned_response.replace('```', '').strip()
        return cleaned_response
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process content generation task"""
        if not self.validate_input(task):
            raise ValueError("Invalid content generation task")
        
        task_type = task.get("type", "generate_content")
        
        if task_type == "generate_content":
            return self.generate_social_content(task)
        else:
            raise ValueError(f"Unsupported content task type: {task_type}")
    
    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate content generation task input"""
        required_fields = ["insight", "research_data"]
        return all(field in task for field in required_fields)
    
    def generate_social_content(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generate multiple social media content pieces from insight and research"""
        insight = task["insight"]
        research_data = task["research_data"]
        content_requirements = task.get("content_requirements", {})
        
        insight_type = insight.get("type", "unknown")
        self.log_decision("content_generation_started", 
                         {"insight_id": insight.get("id", "unknown_id"), "insight_type": insight_type}, 
                         "beginning_content_creation")
        
        try:
            content_pieces = []
            generation_metadata = {
                "insight_id": insight.get("id", "unknown_id"),
                "insight_type": insight_type,
                "content_types_generated": [],
                "total_pieces": 0,
                "quality_scores": []
            }
            
            # Generate content based on insight type and content mix preferences
            if insight.get("type") == "framework" and self.content_mix.get("threads", 0) > 0:
                framework_content = self.generate_framework_thread(insight, research_data)
                if framework_content:
                    content_pieces.append(framework_content)
                    generation_metadata["content_types_generated"].append("framework_thread")
            
            # Generate contrarian content
            if insight.get("contrarian_angle") and self.content_mix.get("single_tweets", 0) > 0:
                contrarian_content = self.generate_contrarian_content(insight, research_data)
                content_pieces.extend(contrarian_content)
                generation_metadata["content_types_generated"].append("contrarian_tweets")
            
            # Generate case study content if research has case studies
            if research_data.get("case_studies") and self.content_mix.get("single_tweets", 0) > 0:
                case_study_content = self.generate_case_study_content(insight, research_data)
                content_pieces.extend(case_study_content)
                generation_metadata["content_types_generated"].append("case_study_content")
            
            # Generate tactical tips
            tactical_content = self.generate_tactical_content(insight, research_data)
            content_pieces.extend(tactical_content)
            generation_metadata["content_types_generated"].append("tactical_tips")
            
            # Validate all content for brand voice and quality
            validated_content = []
            for piece in content_pieces:
                validation_result = self.validate_content_quality(piece)
                
                if validation_result["approved"]:
                    piece["quality_validation"] = validation_result
                    validated_content.append(piece)
                    generation_metadata["quality_scores"].append(validation_result["brand_voice_score"])
                else:
                    self.log_decision("content_rejected",
                                    {"piece_type": piece["type"], 
                                     "brand_score": validation_result.get("brand_voice_score", 0)},
                                    "quality_threshold_not_met")
            
            generation_metadata["total_pieces"] = len(validated_content)
            generation_metadata["avg_quality_score"] = (
                sum(generation_metadata["quality_scores"]) / len(generation_metadata["quality_scores"])
                if generation_metadata["quality_scores"] else 0
            )
            
            self.log_decision("content_generation_completed",
                            {"insight_id": insight.get("id", "unknown_id"), 
                             "pieces_generated": len(validated_content),
                             "avg_quality": generation_metadata["avg_quality_score"]},
                            "content_creation_successful")
            
            # Update performance metrics
            self.update_performance_metrics("insights_processed", 
                                          self.memory.get("performance_metrics", {}).get("insights_processed", 0) + 1)
            self.update_performance_metrics("avg_pieces_per_insight", 
                                          len(validated_content))
            
            # Learn from successful content patterns
            if len(validated_content) >= 3:
                self.learn_from_success({
                    "insight_type": insight.get("type", "unknown"),
                    "content_types": generation_metadata["content_types_generated"],
                    "pieces_count": len(validated_content),
                    "avg_quality": generation_metadata["avg_quality_score"]
                })
            
            self.save_memory()
            
            return {
                "insight_id": insight.get("id", "unknown_id"),
                "content_pieces": validated_content,
                "generation_metadata": generation_metadata,
                "status": "completed"
            }
            
        except Exception as e:
            self.log_decision("content_generation_failed", 
                            {"insight_id": insight.get("id", "unknown_id"), "error": str(e)}, 
                            "content_creation_failed")
            
            # Learn from failure
            self.learn_from_failure({
                "insight_type": insight["type"],
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            
            return {
                "insight_id": insight.get("id", "unknown_id"),
                "content_pieces": [],
                "error": str(e),
                "status": "failed"
            }
    
    def generate_framework_thread(self, insight: Dict[str, Any], research_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Twitter thread breaking down business framework"""
        try:
            prompt = FRAMEWORK_THREAD_PROMPT.format(
                framework_title=insight.get("title", "Unknown"),
                framework_steps=json.dumps(insight.get("steps", [])),
                supporting_research=json.dumps(research_data.get("key_findings", [])),
                case_studies=json.dumps(research_data.get("case_studies", []))
            )
            
            response = self.model_router.generate_content(
                task_type="framework_thread",
                system_prompt=CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=2000,
                agent_name="content_agent"
            )
            
            # Parse thread response
            try:
                cleaned_response = self._clean_json_response(response)
                thread_data = json.loads(cleaned_response)
            except json.JSONDecodeError:
                self.logger.log_error("thread_parse_error", "Failed to parse thread response", 
                                    {"response": response[:500]})
                return None
            
            # Validate thread structure and character limits
            if self._validate_thread_structure(thread_data):
                thread_content = {
                    "type": "thread",
                    "content_subtype": "framework",
                    "thread_tweets": [thread_data["hook_tweet"]] + thread_data["thread_tweets"],
                    "tweet_count": len(thread_data["thread_tweets"]) + 1,
                    "engagement_elements": thread_data.get("engagement_elements", []),
                    "metadata": {
                        "framework_title": insight.get("title", "Unknown"),
                        "character_counts": thread_data.get("character_counts", []),
                        "estimated_engagement": "high"  # Framework threads typically perform well
                    }
                }
                
                return thread_content
            
            return None
            
        except Exception as e:
            self.logger.log_error("framework_thread_error", str(e))
            return None
    
    def generate_contrarian_content(self, insight: Dict[str, Any], research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate contrarian content that challenges conventional wisdom"""
        try:
            prompt = CONTRARIAN_TWEET_PROMPT.format(
                insight_title=insight.get("title", "Unknown"),
                contrarian_angle=insight.get("contrarian_angle", ""),
                supporting_data=json.dumps(research_data.get("supporting_data", [])),
                case_examples=json.dumps(research_data.get("case_studies", []))
            )
            
            response = self.model_router.generate_content(
                task_type="contrarian_content",
                system_prompt=CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=1500,
                agent_name="content_agent"
            )
            
            # Parse contrarian content response
            try:
                cleaned_response = self._clean_json_response(response)
                contrarian_data = json.loads(cleaned_response)
                contrarian_pieces = contrarian_data.get("contrarian_pieces", [])
            except json.JSONDecodeError:
                self.logger.log_error("contrarian_parse_error", "Failed to parse contrarian content response", 
                                    {"response": response[:500]})
                return []
            
            # Convert to standard content format
            formatted_pieces = []
            for piece in contrarian_pieces:
                if piece.get("character_count", 0) <= self.max_tweet_length:
                    formatted_piece = {
                        "type": "single_tweet",
                        "content_subtype": piece["type"],
                        "content": piece["content"],
                        "metadata": {
                            "character_count": piece.get("character_count", len(piece["content"])),
                            "engagement_hook": piece.get("engagement_hook", ""),
                            "contrarian_angle": insight.get("contrarian_angle", "")
                        }
                    }
                    formatted_pieces.append(formatted_piece)
            
            return formatted_pieces
            
        except Exception as e:
            self.logger.log_error("contrarian_content_error", str(e))
            return []
    
    def generate_case_study_content(self, insight: Dict[str, Any], research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate content highlighting case studies and examples"""
        case_studies = research_data.get("case_studies", [])
        if not case_studies:
            return []
        
        try:
            prompt = CASE_STUDY_CONTENT_PROMPT.format(
                case_studies=json.dumps(case_studies),
                business_principle=insight.get("title", "Unknown"),
                key_learning=insight.get("content", "")
            )
            
            response = self.model_router.generate_content(
                task_type="case_study_content",
                system_prompt=CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=1000,
                agent_name="content_agent"
            )
            
            # Parse case study content
            try:
                cleaned_response = self._clean_json_response(response)
                case_study_data = json.loads(cleaned_response)
                case_study_pieces = case_study_data.get("case_study_content", [])
            except json.JSONDecodeError:
                self.logger.log_error("case_study_parse_error", "Failed to parse case study content response", 
                                    {"response": response[:500]})
                return []
            
            # Format case study content
            formatted_pieces = []
            for piece in case_study_pieces:
                if piece.get("character_count", 0) <= self.max_tweet_length:
                    formatted_piece = {
                        "type": "single_tweet",
                        "content_subtype": piece["type"],
                        "content": piece["content"],
                        "metadata": {
                            "character_count": piece.get("character_count", len(piece["content"])),
                            "business_context": piece.get("business_context", ""),
                            "result_focus": piece.get("result_focus", ""),
                            "source_case_studies": len(case_studies)
                        }
                    }
                    formatted_pieces.append(formatted_piece)
            
            return formatted_pieces
            
        except Exception as e:
            self.logger.log_error("case_study_content_error", str(e))
            return []
    
    def generate_tactical_content(self, insight: Dict[str, Any], research_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tactical, actionable tips for SME owners"""
        try:
            prompt = TACTICAL_TIP_PROMPT.format(
                insight_content=insight.get("content", ""),
                research_data=json.dumps(research_data.get("key_findings", [])),
                sme_context=insight.get("business_context", "")
            )
            
            response = self.model_router.generate_content(
                task_type="tactical_content",
                system_prompt=CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=1200,
                agent_name="content_agent"
            )
            
            # Parse tactical tips
            try:
                cleaned_response = self._clean_json_response(response)
                tactical_data = json.loads(cleaned_response)
                tactical_tips = tactical_data.get("tactical_tips", [])
            except json.JSONDecodeError:
                self.logger.log_error("tactical_parse_error", "Failed to parse tactical content response", 
                                    {"response": response[:500]})
                return []
            
            # Format tactical content
            formatted_pieces = []
            for tip in tactical_tips:
                if tip.get("character_count", 0) <= self.max_tweet_length:
                    formatted_piece = {
                        "type": "single_tweet",
                        "content_subtype": "tactical_tip",
                        "content": tip["tip_content"],
                        "metadata": {
                            "character_count": tip.get("character_count", len(tip["tip_content"])),
                            "implementation": tip.get("implementation", ""),
                            "expected_outcome": tip.get("expected_outcome", ""),
                            "timeframe": tip.get("timeframe", "")
                        }
                    }
                    formatted_pieces.append(formatted_piece)
            
            return formatted_pieces
            
        except Exception as e:
            self.logger.log_error("tactical_content_error", str(e))
            return []
    
    def validate_content_quality(self, content_piece: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content against brand voice and quality standards"""
        try:
            prompt = BRAND_VOICE_VALIDATION_PROMPT.format(
                content=json.dumps(content_piece, indent=2)
            )
            
            # Brand voice validation uses Claude via OpenRouter for consistency
            response = self.model_router.generate_content(
                task_type="brand_voice_validation",
                system_prompt=CONTENT_SYSTEM_PROMPT,
                user_prompt=prompt,
                max_tokens=800,
                agent_name="content_agent"
            )
            
            # Parse validation response
            try:
                cleaned_response = self._clean_json_response(response)
                validation_result = json.loads(cleaned_response)
            except json.JSONDecodeError:
                self.logger.log_error("validation_parse_error", "Failed to parse validation response", 
                                    {"response": response[:500]})
                # Fallback validation
                validation_result = self._fallback_validation(content_piece)
            
            # Determine approval based on thresholds
            brand_score = validation_result.get("brand_voice_score", 0)
            approved = (
                brand_score >= self.brand_voice_threshold and
                validation_result.get("approval_recommendation") != "rejected"
            )
            
            validation_result["approved"] = approved
            validation_result["brand_voice_threshold_met"] = brand_score >= self.brand_voice_threshold
            
            return validation_result
            
        except Exception as e:
            self.logger.log_error("content_validation_error", str(e))
            return self._fallback_validation(content_piece)
    
    def _validate_thread_structure(self, thread_data: Dict[str, Any]) -> bool:
        """Validate thread structure and character limits"""
        required_fields = ["hook_tweet", "thread_tweets"]
        if not all(field in thread_data for field in required_fields):
            return False
        
        # Check tweet count is within range
        total_tweets = len(thread_data["thread_tweets"]) + 1  # +1 for hook tweet
        if not (self.thread_length_range[0] <= total_tweets <= self.thread_length_range[1]):
            return False
        
        # Check character limits
        all_tweets = [thread_data["hook_tweet"]] + thread_data["thread_tweets"]
        for tweet in all_tweets:
            if len(tweet) > self.max_tweet_length:
                return False
        
        return True
    
    def _fallback_validation(self, content_piece: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback validation when Claude validation fails"""
        content = content_piece.get("content", "")
        
        # Simple heuristic validation
        brand_score = 0.5  # Neutral score
        
        # Check for brand voice indicators
        contrarian_phrases = ["most SMEs are wrong", "unpopular opinion", "conventional wisdom"]
        if any(phrase.lower() in content.lower() for phrase in contrarian_phrases):
            brand_score += 0.2
        
        # Check for specific data/numbers
        import re
        if re.search(r'\d+%|\$\d+|\d+x', content):
            brand_score += 0.1
        
        # Check length
        if len(content) <= self.max_tweet_length:
            brand_score += 0.1
        
        return {
            "brand_voice_score": min(brand_score, 1.0),
            "evaluation_breakdown": {
                "contrarian_perspective": brand_score,
                "framework_driven": 0.5,
                "data_backed": 0.5,
                "sme_focused": 0.5,
                "practical_actionable": 0.5,
                "direct_tone": 0.5
            },
            "strengths": ["Fallback validation performed"],
            "improvements": ["Manual review recommended"],
            "approval_recommendation": "needs_revision" if brand_score < self.brand_voice_threshold else "approved",
            "approved": brand_score >= self.brand_voice_threshold
        }