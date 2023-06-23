import base64
import hashlib
import logging
from datetime import datetime
from typing import Optional

import pytz
from django.db.models import F
from django.db.transaction import atomic

from django_cloudwatch_metrics.hashing import create_cache_key
from django_cloudwatch_metrics.models import MetricAggregation


@atomic
def increment(metric_name: str, value: int, **kwargs):
    """Publishes a metric increment."""
    datetime_period = datetime.now(pytz.utc).replace(second=0, microsecond=0)

    aggregation_key = create_cache_key(
        metric_name,
        datetime_period,
        kwargs,
    )

    try:
        metric_aggregation, created = MetricAggregation.objects.select_for_update().get_or_create(
            aggregation_key=aggregation_key,
            defaults={
                "datetime_period":  datetime_period,
                "metric_name": metric_name,
                "dimension_data": kwargs,
                "value": value,
            }
        )
    except Exception as e:
        logging.warning(e)
        metric_aggregation = MetricAggregation.objects.select_for_update().filter(aggregation_key=aggregation_key).first()
        created = False

    if not created and metric_aggregation is not None:
        metric_aggregation.value = F("value") + value
        metric_aggregation.save(update_fields=["value"])
