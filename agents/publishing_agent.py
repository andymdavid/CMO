import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from agents.base_agent import BaseAgent
from utils.api_client import TypefullyClient, PublishingError


class PublishingAgent(BaseAgent):
    """
    Publishing agent that handles content scheduling and publication via Typefully,
    implementing intelligent scheduling and error recovery.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("publishing_agent", config)
        self.typefully_client = TypefullyClient(config["typefully_api_key"])
        
        # Configuration
        self.publishing_config = config.get("publishing", {})
        self.posts_per_day = self.publishing_config.get("posts_per_day", 3)
        self.optimal_times = self.publishing_config.get("optimal_times", ["09:00", "14:00", "18:00"])
        self.avoid_weekends = self.publishing_config.get("avoid_weekends", True)
        self.min_thread_spacing_hours = self.publishing_config.get("min_thread_spacing_hours", 48)
        
        # Content scheduling queue
        self.content_queue = []
        self.retry_queue = []
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process publishing task"""
        if not self.validate_input(task):
            raise ValueError("Invalid publishing task")
        
        task_type = task.get("type", "schedule_content")
        
        if task_type == "schedule_content":
            return self.schedule_content_pieces(task)
        elif task_type == "retry_failed":
            return self.retry_failed_publications()
        else:
            raise ValueError(f"Unsupported publishing task type: {task_type}")
    
    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate publishing task input"""
        required_fields = ["content_pieces"]
        return all(field in task for field in required_fields)
    
    def schedule_content_pieces(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule content pieces for publication via Typefully"""
        content_pieces = task["content_pieces"]
        episode_id = task.get("episode_id", "unknown")
        
        if not content_pieces:
            return {
                "episode_id": episode_id,
                "scheduled_content": [],
                "failed_content": [],
                "status": "no_content_to_schedule"
            }
        
        self.log_decision("publishing_started", 
                         {"episode_id": episode_id, "pieces_count": len(content_pieces)}, 
                         "beginning_content_scheduling")
        
        try:
            # Create publishing schedule
            publishing_schedule = self.create_publishing_schedule(content_pieces)
            
            # Schedule each piece of content
            scheduled_content = []
            failed_content = []
            
            for schedule_item in publishing_schedule:
                try:
                    result = self.schedule_single_content(schedule_item)
                    if result["success"]:
                        scheduled_content.append(result)
                        self.log_decision("content_scheduled", 
                                        {"content_type": schedule_item["content"]["type"],
                                         "publish_time": schedule_item["publish_time"].isoformat()}, 
                                        "scheduled_successfully")
                    else:
                        failed_content.append({
                            "content": schedule_item["content"],
                            "error": result["error"],
                            "retry_scheduled": True
                        })
                        # Add to retry queue
                        self.retry_queue.append(schedule_item)
                        
                except Exception as e:
                    self.logger.log_error("scheduling_error", str(e), 
                                        {"content_id": schedule_item["content"].get("id", "unknown")})
                    failed_content.append({
                        "content": schedule_item["content"],
                        "error": str(e),
                        "retry_scheduled": True
                    })
                    self.retry_queue.append(schedule_item)
            
            # Save publishing results
            publishing_summary = {
                "episode_id": episode_id,
                "scheduled_count": len(scheduled_content),
                "failed_count": len(failed_content),
                "scheduled_content": scheduled_content,
                "failed_content": failed_content,
                "next_publication": (
                    min([item["publish_time"] for item in scheduled_content])
                    if scheduled_content else None
                ),
                "publishing_completed_at": datetime.now().isoformat()
            }
            
            self.file_manager.save_published_content(episode_id, publishing_summary)
            
            self.log_decision("publishing_completed",
                            {"episode_id": episode_id, 
                             "scheduled": len(scheduled_content),
                             "failed": len(failed_content)},
                            "content_scheduling_finished")
            
            # Update performance metrics
            self.update_performance_metrics("content_pieces_scheduled", 
                                          self.memory.get("performance_metrics", {}).get("content_pieces_scheduled", 0) + len(scheduled_content))
            self.update_performance_metrics("scheduling_success_rate", 
                                          len(scheduled_content) / len(content_pieces) if content_pieces else 0)
            
            # Learn from publishing patterns
            if len(scheduled_content) >= len(content_pieces) * 0.8:  # 80% success rate
                self.learn_from_success({
                    "episode_id": episode_id,
                    "content_types": [item["content"]["type"] for item in scheduled_content],
                    "scheduling_strategy": "optimal_timing",
                    "success_rate": len(scheduled_content) / len(content_pieces)
                })
            
            self.save_memory()
            
            return {
                "episode_id": episode_id,
                "scheduled_content": scheduled_content,
                "failed_content": failed_content,
                "status": "completed",
                "summary": publishing_summary
            }
            
        except Exception as e:
            self.log_decision("publishing_failed", 
                            {"episode_id": episode_id, "error": str(e)}, 
                            "content_scheduling_failed")
            
            # Learn from failure
            self.learn_from_failure({
                "episode_id": episode_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "content_count": len(content_pieces)
            })
            
            return {
                "episode_id": episode_id,
                "scheduled_content": [],
                "failed_content": content_pieces,
                "error": str(e),
                "status": "failed"
            }
    
    def create_publishing_schedule(self, content_pieces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create optimal publishing schedule for content pieces"""
        schedule_items = []
        
        # Separate content types for strategic scheduling
        threads = [piece for piece in content_pieces if piece["type"] == "thread"]
        single_tweets = [piece for piece in content_pieces if piece["type"] == "single_tweet"]
        
        # Get available time slots for the next 7 days
        time_slots = self.generate_optimal_time_slots()
        
        # Schedule threads first (higher priority, need more spacing)
        thread_slots = self._select_thread_slots(time_slots, len(threads))
        for i, thread in enumerate(threads[:len(thread_slots)]):
            schedule_items.append({
                "content": thread,
                "publish_time": thread_slots[i],
                "priority": "high",
                "content_type": "thread"
            })
        
        # Fill remaining slots with single tweets
        used_slots = set(thread_slots)
        remaining_slots = [slot for slot in time_slots if slot not in used_slots]
        
        for i, single_tweet in enumerate(single_tweets[:len(remaining_slots)]):
            schedule_items.append({
                "content": single_tweet,
                "publish_time": remaining_slots[i],
                "priority": "medium",
                "content_type": "single_tweet"
            })
        
        # Sort by publish time
        schedule_items.sort(key=lambda x: x["publish_time"])
        
        self.log_decision("schedule_created", 
                         {"total_items": len(schedule_items),
                          "threads": len(threads),
                          "single_tweets": len([item for item in schedule_items if item["content_type"] == "single_tweet"])},
                         "publishing_schedule_ready")
        
        return schedule_items
    
    def generate_optimal_time_slots(self) -> List[datetime]:
        """Generate optimal posting times for the next week"""
        time_slots = []
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for day_offset in range(7):  # Next 7 days
            date = current_date + timedelta(days=day_offset)
            
            # Skip weekends if configured
            if self.avoid_weekends and date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                continue
            
            # Add optimal time slots for this day
            for time_str in self.optimal_times[:self.posts_per_day]:
                hour, minute = map(int, time_str.split(':'))
                slot_time = date.replace(hour=hour, minute=minute)
                
                # Only schedule future times (at least 1 hour from now)
                if slot_time > datetime.now() + timedelta(hours=1):
                    time_slots.append(slot_time)
        
        return sorted(time_slots)
    
    def schedule_single_content(self, schedule_item: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a single piece of content via Typefully"""
        content = schedule_item["content"]
        publish_time = schedule_item["publish_time"]
        
        try:
            if content["type"] == "thread":
                # Schedule thread
                thread_tweets = content.get("thread_tweets", [])
                result = self.typefully_client.schedule_post(
                    content=thread_tweets[0] if thread_tweets else "Thread content",
                    publish_time=publish_time,
                    thread_tweets=thread_tweets
                )
            else:
                # Schedule single tweet
                result = self.typefully_client.schedule_post(
                    content=content.get("content", ""),
                    publish_time=publish_time
                )
            
            return {
                "success": True,
                "content": content,
                "publish_time": publish_time.isoformat(),
                "typefully_id": result.get("id"),
                "typefully_response": result
            }
            
        except PublishingError as e:
            self.logger.log_error("typefully_error", str(e), 
                                {"content_type": content["type"], "publish_time": publish_time.isoformat()})
            return {
                "success": False,
                "content": content,
                "publish_time": publish_time.isoformat(),
                "error": str(e)
            }
        
        except Exception as e:
            self.logger.log_error("scheduling_unexpected_error", str(e))
            return {
                "success": False,
                "content": content,
                "publish_time": publish_time.isoformat(),
                "error": str(e)
            }
    
    def retry_failed_publications(self) -> Dict[str, Any]:
        """Retry failed publications from the retry queue"""
        if not self.retry_queue:
            return {
                "retried_count": 0,
                "successful_retries": 0,
                "status": "no_items_to_retry"
            }
        
        self.log_decision("retry_publications_started", 
                         {"items_in_queue": len(self.retry_queue)}, 
                         "beginning_retry_process")
        
        successful_retries = []
        still_failed = []
        
        # Process retry queue
        for schedule_item in self.retry_queue[:]:  # Create copy to avoid modification during iteration
            try:
                # Reschedule for next available slot
                new_time_slots = self.generate_optimal_time_slots()
                if new_time_slots:
                    schedule_item["publish_time"] = new_time_slots[0]
                    result = self.schedule_single_content(schedule_item)
                    
                    if result["success"]:
                        successful_retries.append(result)
                        self.retry_queue.remove(schedule_item)
                    else:
                        still_failed.append(result)
                else:
                    still_failed.append({
                        "content": schedule_item["content"],
                        "error": "No available time slots for retry"
                    })
                    
            except Exception as e:
                still_failed.append({
                    "content": schedule_item["content"],
                    "error": str(e)
                })
        
        self.log_decision("retry_publications_completed",
                         {"successful_retries": len(successful_retries),
                          "still_failed": len(still_failed)},
                         "retry_process_finished")
        
        return {
            "retried_count": len(successful_retries) + len(still_failed),
            "successful_retries": len(successful_retries),
            "still_failed": len(still_failed),
            "successful_items": successful_retries,
            "failed_items": still_failed,
            "status": "completed"
        }
    
    def get_scheduled_content_status(self) -> Dict[str, Any]:
        """Get status of currently scheduled content"""
        try:
            scheduled_posts = self.typefully_client.get_scheduled_posts()
            drafts = self.typefully_client.get_drafts()
            
            return {
                "scheduled_posts_count": len(scheduled_posts),
                "drafts_count": len(drafts),
                "retry_queue_length": len(self.retry_queue),
                "next_scheduled_post": (
                    min([post.get("scheduled_time", "") for post in scheduled_posts])
                    if scheduled_posts else None
                ),
                "status": "healthy"
            }
            
        except Exception as e:
            self.logger.log_error("status_check_error", str(e))
            return {
                "error": str(e),
                "retry_queue_length": len(self.retry_queue),
                "status": "error"
            }
    
    def _select_thread_slots(self, time_slots: List[datetime], thread_count: int) -> List[datetime]:
        """Select optimal time slots for threads with proper spacing"""
        if not time_slots or thread_count == 0:
            return []
        
        selected_slots = []
        min_spacing = timedelta(hours=self.min_thread_spacing_hours)
        
        for slot in time_slots:
            # Check if this slot has proper spacing from already selected slots
            if not selected_slots or all(abs(slot - selected) >= min_spacing for selected in selected_slots):
                selected_slots.append(slot)
                
                # Stop when we have enough slots
                if len(selected_slots) >= thread_count:
                    break
        
        return selected_slots