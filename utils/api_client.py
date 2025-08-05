import anthropic
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


class ClaudeClient:
    """Client for Anthropic Claude API with error handling and rate limiting"""
    
    def __init__(self, api_key: str, config: Optional[Dict[str, Any]] = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        self.logger = AgentLogger("claude_client")
        self.rate_limiter = RateLimiter(calls=10, period=60)  # Much more conservative: 10/minute
        self.cost_monitor = CostMonitor(config or {})
        
        # Token estimation constants
        self.chars_per_token = 4  # Rough estimate: 1 token ≈ 4 characters
    
    def generate_content(self, system_prompt: str, user_prompt: str, 
                        max_tokens: int = 2000, agent_name: str = "unknown",
                        episode_id: Optional[str] = None) -> str:
        """Generate content using Claude API with error handling and cost monitoring"""
        
        # Estimate input tokens
        input_text = system_prompt + user_prompt
        estimated_input_tokens = len(input_text) // self.chars_per_token
        estimated_total_tokens = estimated_input_tokens + max_tokens
        
        # Check cost limits BEFORE making request
        cost_check = self.cost_monitor.check_pre_request_limits(
            agent_name, estimated_total_tokens, episode_id
        )
        
        if not cost_check["allowed"]:
            error_msg = f"Request blocked by cost limits: {'; '.join(cost_check['reasons'])}"
            self.logger.log_error("cost_limit_blocked", error_msg, cost_check)
            raise ContentGenerationError(error_msg)
        
        # Log cost estimate
        self.logger.log_info("api_request_starting", {
            "agent": agent_name,
            "estimated_tokens": estimated_total_tokens,
            "estimated_cost_usd": cost_check["estimated_cost_usd"],
            "episode_id": episode_id
        })
        
        self.rate_limiter.wait_if_needed()
        start_time = time.time()
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            end_time = time.time()
            
            # Record actual usage
            actual_input_tokens = response.usage.input_tokens
            actual_output_tokens = response.usage.output_tokens
            
            self.cost_monitor.record_api_usage(
                agent_name, actual_input_tokens, actual_output_tokens, 
                episode_id, success=True
            )
            
            self.logger.log_api_call("claude", "messages.create", True, end_time - start_time)
            self.logger.log_info("api_usage_actual", {
                "agent": agent_name,
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
                "total_tokens": actual_input_tokens + actual_output_tokens,
                "cost_usd": round((actual_input_tokens * 0.000003) + (actual_output_tokens * 0.000015), 4)
            })
            
            return response.content[0].text
            
        except anthropic.RateLimitError as e:
            self.logger.log_api_call("claude", "messages.create", False, time.time() - start_time)
            self.logger.log_error("rate_limit_error", str(e))
            # Wait and retry once with exponential backoff
            wait_time = 60 + (time.time() % 30)  # 60-90 seconds
            time.sleep(wait_time)
            return self.generate_content(system_prompt, user_prompt, max_tokens, agent_name, episode_id)
            
        except anthropic.APIError as e:
            self.logger.log_api_call("claude", "messages.create", False, time.time() - start_time)
            self.logger.log_error("api_error", str(e))
            raise ContentGenerationError(f"Claude API error: {e}")
            
        except Exception as e:
            self.logger.log_api_call("claude", "messages.create", False, time.time() - start_time)
            self.logger.log_error("unexpected_error", str(e))
            raise ContentGenerationError(f"Unexpected error: {e}")


class TypefullyClient:
    """Client for Typefully API with error handling and rate limiting"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.typefully.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.logger = AgentLogger("typefully_client")
        self.rate_limiter = RateLimiter(calls=30, period=3600)  # Free tier limits
    
    def create_draft(self, content: str, thread_tweets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a draft post in Typefully"""
        self.rate_limiter.wait_if_needed()
        
        payload = {
            "content": content,
            "status": "draft"
        }
        
        if thread_tweets:
            payload["tweets"] = thread_tweets
        
        return self._make_request("POST", "/drafts", payload)
    
    def schedule_post(self, content: str, publish_time: datetime, 
                     thread_tweets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Schedule content for publication via Typefully"""
        self.rate_limiter.wait_if_needed()
        
        payload = {
            "content": content,
            "schedule_time": publish_time.isoformat(),
            "status": "scheduled"
        }
        
        if thread_tweets:
            payload["tweets"] = thread_tweets
        
        return self._make_request("POST", "/posts", payload)
    
    def get_drafts(self) -> List[Dict[str, Any]]:
        """Get all draft posts"""
        return self._make_request("GET", "/drafts")
    
    def get_scheduled_posts(self) -> List[Dict[str, Any]]:
        """Get all scheduled posts"""
        return self._make_request("GET", "/posts", params={"status": "scheduled"})
    
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