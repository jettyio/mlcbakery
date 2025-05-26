from opentelemetry.metrics import get_meter_provider

NAME_SEARCH_QUERIES_TOTAL = "mlcbakery.search.queries_total"
_METRICS = {}
def init_metrics():
    # Initialize a meter
    meter = get_meter_provider().get_meter("mlcbakery.meter")
    _METRICS[NAME_SEARCH_QUERIES_TOTAL] = meter.create_counter(
    name=NAME_SEARCH_QUERIES_TOTAL,
    description="Counts the total number of search queries processed."
)

def get_metric(name: str):
    return _METRICS.get(name)