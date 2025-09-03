import json
import os
import time
from datetime import datetime
from threading import Lock
import logging

logger = logging.getLogger(__name__)

# Thread-safe cost tracking
cost_lock = Lock()

class GeminiCostTracker:
    """Track costs for Gemini API calls with detailed logging."""
    
    # Gemini pricing per 1M tokens
    PRICING = {
        'input': {
            'tier1': 1.25,  # <= 200k tokens
            'tier2': 2.50,  # > 200k tokens
            'threshold': 200000
        },
        'output': {
            'tier1': 10.00,  # <= 200k tokens
            'tier2': 15.00,  # > 200k tokens
            'threshold': 200000
        }
    }
    
    def __init__(self, pdf_dir, filename):
        self.pdf_dir = pdf_dir
        self.filename = filename
        self.cost_log_path = os.path.join(pdf_dir, 'cost_log.json')
        self.cost_summary_path = os.path.join(pdf_dir, 'cost_summary.json')
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0
        self.calls_log = []
        
    def calculate_cost(self, input_tokens, output_tokens):
        """Calculate cost based on token usage and pricing tiers."""
        input_cost = self._calculate_tier_cost(input_tokens, 'input')
        output_cost = self._calculate_tier_cost(output_tokens, 'output')
        total_cost = input_cost + output_cost
        
        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost
        }
    
    def _calculate_tier_cost(self, tokens, token_type):
        """Calculate cost for specific token type with tier pricing."""
        if tokens == 0:
            return 0.0
            
        pricing = self.PRICING[token_type]
        
        if tokens <= pricing['threshold']:
            # Tier 1 pricing
            cost = (tokens / 1_000_000) * pricing['tier1']
        else:
            # Tier 2 pricing for all tokens
            cost = (tokens / 1_000_000) * pricing['tier2']
            
        return cost
    
    def log_api_call(self, operation, page_num, input_tokens, output_tokens, duration=None):
        """Log individual API call with cost calculation."""
        with cost_lock:
            cost_data = self.calculate_cost(input_tokens, output_tokens)
            
            call_record = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,  # 'transcription' or 'translation'
                'page': page_num,
                'duration_seconds': duration,
                **cost_data
            }
            
            self.calls_log.append(call_record)
            self.total_cost += cost_data['total_cost']
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.call_count += 1
            
            # Log the call
            logger.info(f"[{self.filename}] API Call - {operation} page {page_num}: "
                       f"${cost_data['total_cost']:.6f} "
                       f"(in: {input_tokens}, out: {output_tokens})")
            
            return call_record
    
    def save_cost_log(self):
        """Save detailed cost log to JSON file."""
        try:
            with open(self.cost_log_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'filename': self.filename,
                    'total_calls': self.call_count,
                    'total_cost': self.total_cost,
                    'total_input_tokens': self.total_input_tokens,
                    'total_output_tokens': self.total_output_tokens,
                    'calls': self.calls_log
                }, f, indent=2)
            
            logger.info(f"[{self.filename}] Cost log saved: {self.cost_log_path}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.filename}] Failed to save cost log: {e}")
            return False
    
    def save_cost_summary(self):
        """Save cost summary for easy access."""
        try:
            # Calculate breakdown by operation
            transcription_cost = sum(call['total_cost'] for call in self.calls_log 
                                   if call['operation'] == 'transcription')
            translation_cost = sum(call['total_cost'] for call in self.calls_log 
                                 if call['operation'] == 'translation')
            
            transcription_calls = len([call for call in self.calls_log 
                                     if call['operation'] == 'transcription'])
            translation_calls = len([call for call in self.calls_log 
                                   if call['operation'] == 'translation'])
            
            summary = {
                'filename': self.filename,
                'timestamp': datetime.now().isoformat(),
                'total_cost': self.total_cost,
                'total_input_tokens': self.total_input_tokens,
                'total_output_tokens': self.total_output_tokens,
                'total_calls': self.call_count,
                'breakdown': {
                    'transcription': {
                        'cost': transcription_cost,
                        'calls': transcription_calls,
                        'avg_cost_per_call': transcription_cost / transcription_calls if transcription_calls > 0 else 0
                    },
                    'translation': {
                        'cost': translation_cost,
                        'calls': translation_calls,
                        'avg_cost_per_call': translation_cost / translation_calls if translation_calls > 0 else 0
                    }
                },
                'cost_per_page': self.total_cost / max(1, len(set(call['page'] for call in self.calls_log))),
                'pricing_info': {
                    'input_tier1': f"${self.PRICING['input']['tier1']}/1M tokens (≤200k)",
                    'input_tier2': f"${self.PRICING['input']['tier2']}/1M tokens (>200k)",
                    'output_tier1': f"${self.PRICING['output']['tier1']}/1M tokens (≤200k)",
                    'output_tier2': f"${self.PRICING['output']['tier2']}/1M tokens (>200k)"
                }
            }
            
            with open(self.cost_summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"[{self.filename}] Cost summary saved: ${self.total_cost:.6f} total")
            return summary
            
        except Exception as e:
            logger.error(f"[{self.filename}] Failed to save cost summary: {e}")
            return None
    
    def get_summary(self):
        """Get current cost summary without saving."""
        return {
            'total_cost': self.total_cost,
            'total_calls': self.call_count,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens
        }

def extract_token_usage(response):
    """Extract token usage from Gemini API response."""
    try:
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0)
            output_tokens = getattr(usage, 'candidates_token_count', 0)
            return input_tokens, output_tokens
        else:
            # Fallback: estimate tokens if usage metadata not available
            # Rough estimation: ~4 characters per token
            input_tokens = 0  # Can't estimate input without knowing the prompt
            output_tokens = len(response.text) // 4 if hasattr(response, 'text') else 0
            logger.warning("Token usage metadata not available, using estimation")
            return input_tokens, output_tokens
            
    except Exception as e:
        logger.error(f"Failed to extract token usage: {e}")
        return 0, 0
