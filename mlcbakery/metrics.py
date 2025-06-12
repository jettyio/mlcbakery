from opentelemetry.metrics import get_meter_provider, Counter

NAME_SEARCH_QUERIES_TOTAL = "mlcbakery.search.queries_total"
_METRICS = {}
def init_metrics():
    # Initialize a meter
    meter = get_meter_provider().get_meter("mlcbakery.meter")
    _METRICS[NAME_SEARCH_QUERIES_TOTAL] = meter.create_counter(
    name=NAME_SEARCH_QUERIES_TOTAL,
    description="Counts the total number of search queries processed."
)

def get_metric(name: str) -> Counter:
    return _METRICS.get(name)

def increment_metric(name: str, value: int = 1):
    if name not in _METRICS:
        raise ValueError(f"Metric {name} not found")
    _METRICS[name].add(value)