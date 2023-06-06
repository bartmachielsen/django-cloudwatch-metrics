import base64
import hashlib
from datetime import datetime
from typing import Optional

import pytz
from django.db.models import F

from django_cloudwatch_metrics.hashing import create_cache_key
from django_cloudwatch_metrics.models import MetricAggregation


def increment(metric_name: str, value: int, **kwargs):
    """Publishes a metric increment."""
    datetime_period = datetime.now(pytz.utc).replace(second=0, microsecond=0)

    aggregation_hash_key = create_cache_key(
        metric_name,
        datetime_period,
        kwargs,
    )

    try:
        metric_aggregation, created = MetricAggregation.objects.get_or_create(
            aggregation_key=aggregation_hash_key,
            defaults={
                "datetime_period":  datetime_period,
                "metric_name": metric_name,
                "dimension_data": kwargs,
                "value": value,
            }
        )
    except MetricAggregation.MultipleObjectsReturned:
        metric_aggregation = MetricAggregation.objects.filter(
            aggregation_key=aggregation_hash_key
        ).first()
        created = False

    if created:
        return

    if metric_aggregation:
        metric_aggregation.value = F("value") + value
        metric_aggregation.save(update_fields=["value"])