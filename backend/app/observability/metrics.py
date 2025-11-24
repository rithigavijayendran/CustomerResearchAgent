"""
Prometheus Metrics for Observability
Tracks: request counts, latency, errors, cache hits, job status
"""

import time
import logging
from functools import wraps
from typing import Callable, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# Research metrics
research_requests_total = Counter(
    'research_requests_total',
    'Total research requests',
    ['company', 'status']
)

research_duration = Histogram(
    'research_duration_seconds',
    'Research duration in seconds',
    ['company']
)

# Cache metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

# Job metrics
background_jobs_total = Counter(
    'background_jobs_total',
    'Total background jobs',
    ['job_type', 'status']
)

background_job_duration = Histogram(
    'background_job_duration_seconds',
    'Background job duration in seconds',
    ['job_type']
)

# Vector store metrics
vector_store_operations_total = Counter(
    'vector_store_operations_total',
    'Total vector store operations',
    ['operation', 'status']
)

vector_store_duration = Histogram(
    'vector_store_duration_seconds',
    'Vector store operation duration in seconds',
    ['operation']
)

# LLM metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'status']
)

llm_request_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider', 'model']
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens',
    ['provider', 'model', 'type']  # type: prompt or completion
)

# Active jobs gauge
active_jobs = Gauge(
    'active_jobs',
    'Number of active jobs',
    ['job_type']
)

# WebSocket metrics
websocket_connections_total = Counter(
    'websocket_connections_total',
    'Total WebSocket connections',
    ['status']
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total WebSocket messages',
    ['type']
)


def track_http_request(method: str, endpoint: str, status: int, duration: float):
    """Track HTTP request metrics"""
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def track_research(company: str, status: str, duration: float):
    """Track research metrics"""
    research_requests_total.labels(company=company, status=status).inc()
    research_duration.labels(company=company).observe(duration)


def track_cache_hit(cache_type: str):
    """Track cache hit"""
    cache_hits_total.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str):
    """Track cache miss"""
    cache_misses_total.labels(cache_type=cache_type).inc()


def track_background_job(job_type: str, status: str, duration: float):
    """Track background job metrics"""
    background_jobs_total.labels(job_type=job_type, status=status).inc()
    background_job_duration.labels(job_type=job_type).observe(duration)


def track_vector_store_operation(operation: str, status: str, duration: float):
    """Track vector store operation metrics"""
    vector_store_operations_total.labels(operation=operation, status=status).inc()
    vector_store_duration.labels(operation=operation).observe(duration)


def track_llm_request(provider: str, model: str, status: str, duration: float, prompt_tokens: int = 0, completion_tokens: int = 0):
    """Track LLM request metrics"""
    llm_requests_total.labels(provider=provider, model=model, status=status).inc()
    llm_request_duration.labels(provider=provider, model=model).observe(duration)
    
    if prompt_tokens > 0:
        llm_tokens_total.labels(provider=provider, model=model, type="prompt").inc(prompt_tokens)
    if completion_tokens > 0:
        llm_tokens_total.labels(provider=provider, model=model, type="completion").inc(completion_tokens)


def track_websocket_connection(status: str):
    """Track WebSocket connection"""
    websocket_connections_total.labels(status=status).inc()


def track_websocket_message(message_type: str):
    """Track WebSocket message"""
    websocket_messages_total.labels(type=message_type).inc()


def update_active_jobs(job_type: str, count: int):
    """Update active jobs gauge"""
    active_jobs.labels(job_type=job_type).set(count)


def metrics_middleware(func: Callable) -> Callable:
    """Decorator to track function metrics"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            # Track success (implement specific tracking based on function)
            return result
        except Exception as e:
            duration = time.time() - start_time
            # Track error (implement specific tracking based on function)
            raise
    return wrapper


def get_metrics():
    """Get Prometheus metrics"""
    return generate_latest()

