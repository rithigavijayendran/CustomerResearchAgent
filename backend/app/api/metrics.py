"""
Prometheus metrics endpoint
"""

from fastapi import APIRouter
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from fastapi.responses import Response
import time

router = APIRouter()

# Helper to safely create metrics (handles duplicate registration during hot reload)
def safe_create_counter(name, description, labels=None):
    """Create counter, reusing existing if already registered"""
    try:
        if labels:
            return Counter(name, description, labels)
        else:
            return Counter(name, description)
    except ValueError:
        # Metric already exists - find and return it
        # This happens during uvicorn hot reload
        try:
            # Try to get from registry
            for collector in list(REGISTRY._collector_to_names.keys()):
                if hasattr(collector, '_name') and collector._name == name:
                    return collector
        except:
            pass
        # If we can't find it, create a dummy that won't be used
        # (This should rarely happen)
        class DummyMetric:
            def inc(self, *args, **kwargs): pass
            def observe(self, *args, **kwargs): pass
            def set(self, *args, **kwargs): pass
        return DummyMetric()

def safe_create_histogram(name, description, labels=None):
    """Create histogram, reusing existing if already registered"""
    try:
        if labels:
            return Histogram(name, description, labels)
        else:
            return Histogram(name, description)
    except ValueError:
        try:
            for collector in list(REGISTRY._collector_to_names.keys()):
                if hasattr(collector, '_name') and collector._name == name:
                    return collector
        except:
            pass
        class DummyMetric:
            def inc(self, *args, **kwargs): pass
            def observe(self, *args, **kwargs): pass
            def set(self, *args, **kwargs): pass
        return DummyMetric()

def safe_create_gauge(name, description, labels=None):
    """Create gauge, reusing existing if already registered"""
    try:
        if labels:
            return Gauge(name, description, labels)
        else:
            return Gauge(name, description)
    except ValueError:
        try:
            for collector in list(REGISTRY._collector_to_names.keys()):
                if hasattr(collector, '_name') and collector._name == name:
                    return collector
        except:
            pass
        class DummyMetric:
            def inc(self, *args, **kwargs): pass
            def observe(self, *args, **kwargs): pass
            def set(self, *args, **kwargs): pass
        return DummyMetric()

# Metrics - safely create to prevent duplicate registration errors
http_requests_total = safe_create_counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = safe_create_histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

active_connections = safe_create_gauge(
    'active_connections',
    'Number of active connections'
)

chat_messages_total = safe_create_counter(
    'chat_messages_total',
    'Total chat messages',
    ['role']
)

plan_regenerations_total = safe_create_counter(
    'plan_regenerations_total',
    'Total plan section regenerations',
    ['section']
)

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

