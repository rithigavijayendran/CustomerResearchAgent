"""
Observability Module
Logging, tracing, and metrics for monitoring system performance
"""

import logging
import time
import functools
from typing import Dict, Optional, Any, Callable
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class TraceContext:
    """
    Trace context for request tracing
    """
    
    def __init__(self, trace_id: Optional[str] = None, span_id: Optional[str] = None):
        """
        Initialize trace context
        
        Args:
            trace_id: Trace ID (generated if not provided)
            span_id: Span ID (generated if not provided)
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.start_time = time.time()
        self.spans = []
    
    def create_span(self, name: str) -> 'Span':
        """Create a new span"""
        span = Span(name, self.trace_id)
        self.spans.append(span)
        return span
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "duration_ms": (time.time() - self.start_time) * 1000,
            "spans": [span.to_dict() for span in self.spans]
        }


class Span:
    """
    Span for tracing individual operations
    """
    
    def __init__(self, name: str, trace_id: str):
        """
        Initialize span
        
        Args:
            name: Span name
            trace_id: Parent trace ID
        """
        self.name = name
        self.trace_id = trace_id
        self.span_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.end_time = None
        self.attributes = {}
        self.events = []
    
    def set_attribute(self, key: str, value: Any):
        """Set span attribute"""
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict] = None):
        """Add event to span"""
        self.events.append({
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "attributes": attributes or {}
        })
    
    def end(self):
        """End span"""
        self.end_time = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else None,
            "attributes": self.attributes,
            "events": self.events
        }


def trace_function(name: Optional[str] = None):
    """
    Decorator to trace function execution
    
    Args:
        name: Optional span name (defaults to function name)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__name__}"
            span = Span(span_name, "auto")
            
            try:
                span.set_attribute("function", func.__name__)
                span.set_attribute("module", func.__module__)
                
                start = time.time()
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                
                span.set_attribute("duration_ms", duration)
                span.set_attribute("success", True)
                span.end()
                
                logger.debug(f"Trace: {span_name} completed in {duration:.2f}ms")
                return result
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                span.end()
                logger.error(f"Trace: {span_name} failed: {e}")
                raise
        
        return wrapper
    return decorator


class MetricsCollector:
    """
    Simple metrics collector
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        self.metrics = {}
    
    def increment(self, metric_name: str, value: float = 1.0, tags: Optional[Dict] = None):
        """
        Increment a counter metric
        
        Args:
            metric_name: Metric name
            value: Increment value
            tags: Optional tags
        """
        key = self._make_key(metric_name, tags)
        self.metrics[key] = self.metrics.get(key, 0) + value
    
    def record(self, metric_name: str, value: float, tags: Optional[Dict] = None):
        """
        Record a value metric
        
        Args:
            metric_name: Metric name
            value: Value to record
            tags: Optional tags
        """
        key = self._make_key(metric_name, tags)
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(value)
    
    def _make_key(self, metric_name: str, tags: Optional[Dict]) -> str:
        """Make metric key from name and tags"""
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{metric_name}[{tag_str}]"
        return metric_name
    
    def get_metrics(self) -> Dict:
        """Get all metrics"""
        return self.metrics.copy()


# Global metrics collector
_metrics_collector = MetricsCollector()

def get_metrics() -> MetricsCollector:
    """Get global metrics collector"""
    return _metrics_collector

