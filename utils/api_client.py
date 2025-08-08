import openai
import requests
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from utils.logger import AgentLogger
from utils.cost_monitor import CostMonitor


class ContentGenerationError(Exception):
    """Exception raised when content generation fails"""
    pass


class PublishingError(Exception):
    """Exception raised when publishing fails"""
    pass


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, calls: int, period: int):
        self.calls = calls
        self.period = period
        self.call_times = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old calls outside the period
        self.call_times = [t for t in self.call_times if now - t < self.period]
        
        # If we're at the limit, wait
        if len(self.call_times) >= self.calls:
            sleep_time = self.period - (now - self.call_times[0]) + 1
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Record this call
        self.call_times.append(now)


# Removed ClaudeClient - all calls now go through OpenRouter


class TypefullyClient:
    """Client for Typefully API with error handling and rate limiting"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.typefully.com"
        self.headers = {
            "X-API-KEY": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.logger = AgentLogger("typefully_client")
        self.rate_limiter = RateLimiter(calls=30, period=3600)  # Free tier limits
    
    def create_draft(self, content: str, thread_tweets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a draft post in Typefully"""
        self.rate_limiter.wait_if_needed()
        
        if thread_tweets:
            # For threads, join all tweets with newlines - Typefully will auto-split
            full_content = "\n\n".join([content] + thread_tweets)
        else:
            full_content = content
        
        payload = {
            "content": full_content
        }
        
        return self._make_request("POST", "/v1/drafts/", payload)
    
    def schedule_post(self, content: str, publish_time: datetime, 
                     thread_tweets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Schedule content for publication via Typefully"""
        self.rate_limiter.wait_if_needed()
        
        if thread_tweets:
            # For threads, join all tweets with newlines - Typefully will auto-split
            full_content = "\n\n".join([content] + thread_tweets)
        else:
            full_content = content
        
        payload = {
            "content": full_content,
            "schedule-date": publish_time.isoformat()
        }
        
        return self._make_request("POST", "/v1/drafts/", payload)
    
    def get_drafts(self) -> List[Dict[str, Any]]:
        """Get all draft posts"""
        return self._make_request("GET", "/v1/drafts/recently-scheduled/")
    
    def get_scheduled_posts(self) -> List[Dict[str, Any]]:
        """Get all scheduled posts"""
        return self._make_request("GET", "/v1/drafts/recently-scheduled/")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, 
                     params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make HTTP request to Typefully API"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            end_time = time.time()
            
            if response.status_code in [200, 201]:
                self.logger.log_api_call("typefully", endpoint, True, end_time - start_time)
                return response.json()
            else:
                self.logger.log_api_call("typefully", endpoint, False, end_time - start_time)
                self.logger.log_error("api_error", 
                                    f"HTTP {response.status_code}: {response.text}",
                                    {"endpoint": endpoint, "method": method})
                raise PublishingError(f"Typefully API error: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            self.logger.log_api_call("typefully", endpoint, False, time.time() - start_time)
            self.logger.log_error("network_error", str(e), {"endpoint": endpoint, "method": method})
            raise PublishingError(f"Network error: {e}")
        
        except ValueError as e:
            self.logger.log_error("request_error", str(e), {"endpoint": endpoint, "method": method})
            raise PublishingError(f"Request error: {e}")


class OpenRouterClient:
    """Unified client for all models via OpenRouter API"""
    
    def __init__(self, api_key: str, config: Optional[Dict[str, Any]] = None):
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.logger = AgentLogger("openrouter_client")
        self.rate_limiter = RateLimiter(calls=30, period=60)
        self.cost_monitor = CostMonitor(config or {})
        
        # Model-specific pricing (per 1M tokens)
        self.model_pricing = {
            "anthropic/claude-3-5-sonnet": {
                "input": 3.00,   # $3 per 1M input tokens
                "output": 15.00  # $15 per 1M output tokens
            },
            "deepseek/deepseek-chat": {
                "input": 0.14,   # $0.14 per 1M input tokens
                "output": 0.28   # $0.28 per 1M output tokens
            },
            "deepseek/deepseek-reasoner": {
                "input": 0.55,   # $0.55 per 1M input tokens
                "output": 2.19   # $2.19 per 1M output tokens
            }
        }
        
        # Token estimation
        self.chars_per_token = 4
    
    def generate_content(self, system_prompt: str, user_prompt: str,
                        model: str = "deepseek/deepseek-chat",
                        max_tokens: int = 2000, agent_name: str = "unknown",
                        episode_id: Optional[str] = None) -> str:
        """Generate content using OpenRouter API with any model"""
        
        # Get model-specific pricing
        model_costs = self.model_pricing.get(model, self.model_pricing["deepseek/deepseek-chat"])
        
        # Estimate input tokens
        input_text = system_prompt + user_prompt
        estimated_input_tokens = len(input_text) // self.chars_per_token
        estimated_total_tokens = estimated_input_tokens + max_tokens
        
        # Check cost limits BEFORE making request
        cost_check = self.cost_monitor.check_pre_request_limits(
            f"{agent_name}_{model.replace('/', '_')}", estimated_total_tokens, episode_id
        )
        
        if not cost_check["allowed"]:
            error_msg = f"OpenRouter request blocked by cost limits: {'; '.join(cost_check['reasons'])}"
            self.logger.log_error("cost_limit_blocked", error_msg, cost_check)
            raise ContentGenerationError(error_msg)
        
        # Log cost estimate
        estimated_cost = (estimated_input_tokens * model_costs["input"] / 1000000) + \
                        (max_tokens * model_costs["output"] / 1000000)
        self.logger.log_info("openrouter_request_starting", {
            "agent": agent_name,
            "model": model,
            "estimated_tokens": estimated_total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "episode_id": episode_id
        })
        
        self.rate_limiter.wait_if_needed()
        start_time = time.time()
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            
            end_time = time.time()
            
            # Record actual usage
            actual_input_tokens = response.usage.prompt_tokens
            actual_output_tokens = response.usage.completion_tokens
            
            self.cost_monitor.record_api_usage(
                f"{agent_name}_{model.replace('/', '_')}", actual_input_tokens, 
                actual_output_tokens, episode_id, success=True
            )
            
            actual_cost = (actual_input_tokens * model_costs["input"] / 1000000) + \
                         (actual_output_tokens * model_costs["output"] / 1000000)
            
            self.logger.log_api_call("openrouter", model, True, end_time - start_time)
            self.logger.log_info("openrouter_usage_actual", {
                "agent": agent_name,
                "model": model,
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "total_tokens": actual_input_tokens + actual_output_tokens,
                "cost_usd": round(actual_cost, 6)
            })
            
            return response.choices[0].message.content
            
        except openai.RateLimitError as e:
            self.logger.log_api_call("openrouter", model, False, time.time() - start_time)
            self.logger.log_error("rate_limit_error", str(e))
            # Wait and retry once
            wait_time = 30 + (time.time() % 15)  # 30-45 seconds
            time.sleep(wait_time)
            return self.generate_content(system_prompt, user_prompt, model, max_tokens, agent_name, episode_id)
            
        except openai.APIError as e:
            self.logger.log_api_call("openrouter", model, False, time.time() - start_time)
            self.logger.log_error("openrouter_api_error", str(e))
            raise ContentGenerationError(f"OpenRouter API error: {e}")
            
        except Exception as e:
            self.logger.log_api_call("openrouter", model, False, time.time() - start_time)
            self.logger.log_error("openrouter_unexpected_error", str(e))
            raise ContentGenerationError(f"OpenRouter unexpected error: {e}")


class ModelRouter:
    """Intelligent router that selects optimal models for different tasks via OpenRouter"""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.openrouter_client = openrouter_client
        self.logger = AgentLogger("model_router")
        
        # Task to model mapping - all via OpenRouter
        self.task_models = {
            # High complexity - requires Claude's reasoning via OpenRouter
            "insight_extraction": "anthropic/claude-3-5-sonnet",
            "insight_prioritization": "anthropic/claude-3-5-sonnet", 
            "research_analysis": "anthropic/claude-3-5-sonnet",
            "brand_voice_validation": "anthropic/claude-3-5-sonnet",
            
            # Medium/Low complexity - use cheaper models
            "content_generation": "deepseek/deepseek-chat",
            "framework_thread": "deepseek/deepseek-chat",
            "contrarian_content": "deepseek/deepseek-chat",
            "case_study_content": "deepseek/deepseek-chat",
            "tactical_content": "deepseek/deepseek-chat",
            "search_query_generation": "deepseek/deepseek-chat"
        }
        
        # Fallback model for unknown tasks
        self.default_model = "deepseek/deepseek-chat"
    
    def generate_content(self, task_type: str, system_prompt: str, user_prompt: str,
                        max_tokens: int = 2000, agent_name: str = "unknown",
                        episode_id: Optional[str] = None) -> str:
        """Route request to optimal model based on task complexity via OpenRouter"""
        
        # Determine which model to use
        selected_model = self.task_models.get(task_type, self.default_model)
        
        self.logger.log_info("routing_request", {
            "task_type": task_type,
            "selected_model": selected_model,
            "agent": agent_name,
            "episode_id": episode_id
        })
        
        # All requests go through OpenRouter
        return self.openrouter_client.generate_content(
            system_prompt, user_prompt, selected_model, max_tokens, agent_name, episode_id
        )
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost breakdown by model type"""
        return {
            "routing_strategy": "All via OpenRouter - Claude for reasoning, DeepSeek for content",
            "expected_cost_reduction": "~85-90% overall with intelligent model selection",
            "task_models": self.task_models,
            "reasoning_model": "anthropic/claude-3-5-sonnet",
            "content_model": "deepseek/deepseek-chat"
        }


class WebSearchClient:
    """Client for web search functionality using Claude Code's built-in capabilities"""
    
    def __init__(self):
        self.logger = AgentLogger("web_search_client")
    
    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Perform web search using Claude Code's built-in search.
        Note: This will be replaced with actual web_search calls in Claude Code environment.
        """
        self.logger.log_info(f"Performing web search: {query}", {"max_results": max_results})
        
        # In Claude Code environment, this becomes:
        # from claude_code import web_search
        # return web_search(query, max_results=max_results)
        
        # For testing/development, return simulated results
        return self._simulate_search_results(query, max_results)
    
    def search_with_openrouter(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Enhanced search with OpenRouter for query optimization"""
        # Note: In production, this could use OpenRouter to optimize search queries
        # For now, falls back to standard search
        return self.search(query, max_results)
    
    def _simulate_search_results(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Simulate search results for testing purposes"""
        return [
            {
                "title": f"Search result {i+1} for: {query}",
                "url": f"https://example.com/result-{i+1}",
                "snippet": f"This is a simulated search result snippet for query '{query}'. "
                          f"It contains relevant information for testing purposes.",
                "source": "example.com",
                "relevance_score": 0.9 - (i * 0.1),
                "credibility_score": 0.8
            }
            for i in range(min(max_results, 5))
        ]