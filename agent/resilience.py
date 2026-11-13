import os, time, json, hashlib
import redis

# Circuit breaker configuration (A5)
FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 30.0

_cb_state = {
    "failures": 0,
    "last_failure_time": 0.0,
    "state": "CLOSED"  # CLOSED, OPEN, HALF-OPEN
}

def can_call_provider() -> bool:
    """Returns True if circuit is CLOSED or ready to test in HALF-OPEN (A5)."""
    state = _cb_state["state"]
    if state == "CLOSED":
        return True
    now = time.time()
    if state == "OPEN":
        if now - _cb_state["last_failure_time"] >= COOLDOWN_SECONDS:
            _cb_state["state"] = "HALF-OPEN"
            return True
        return False
    return True  # HALF-OPEN allows one trial request

def record_success():
    _cb_state["failures"] = 0
    _cb_state["state"] = "CLOSED"

def record_failure():
    _cb_state["failures"] += 1
    _cb_state["last_failure_time"] = time.time()
    if _cb_state["failures"] >= FAILURE_THRESHOLD:
        _cb_state["state"] = "OPEN"
        print(f"[circuit_breaker] OPEN! Failures={_cb_state['failures']}. Cooldown={COOLDOWN_SECONDS}s")

# Redis retrieval caching (D7)
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    return _redis_client

def get_cached(key_prefix: str, query: str):
    r = _get_redis()
    if not r:
        return None
    try:
        h = hashlib.sha256(query.encode()).hexdigest()[:16]
        val = r.get(f"cache:{key_prefix}:{h}")
        return json.loads(val) if val else None
    except Exception:
        return None

def set_cached(key_prefix: str, query: str, data, ttl_seconds: int = 3600):
    r = _get_redis()
    if not r:
        return
    try:
        h = hashlib.sha256(query.encode()).hexdigest()[:16]
        r.set(f"cache:{key_prefix}:{h}", json.dumps(data), ex=ttl_seconds)
    except Exception:
        pass
