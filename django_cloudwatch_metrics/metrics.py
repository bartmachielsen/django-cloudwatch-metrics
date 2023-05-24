from datetime import datetime
from typing import Optional

import pytz
from django.db.models import F

from django_cloudwatch_metrics.models import MetricAggregation


def increment(metric_name: str, value: int, dimension_name: Optional[str] = None, dimension_value: Optional[str] = None):
    """Publishes a metric increment."""
    datetime_period = datetime.now(pytz.utc).replace(second=0, microsecond=0)
    metric_aggregation, created = MetricAggregation.objects.get_or_create(
        datetime_period=datetime_period,
        metric_name=metric_name,
        dimension_name=dimension_name,
        dimension_value=dimension_value,
        defaults={
            "value": value,
        }
    )
    if created:
        return

    metric_aggregation.value = F("value") + value
    metric_aggregation.save(update_fields=["value"])