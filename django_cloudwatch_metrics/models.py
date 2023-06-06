from django.db import models


class MetricAggregation(models.Model):
    """Metric Aggregation."""
    aggregation_key = models.CharField(max_length=255, unique=True)

    datetime_period = models.DateTimeField(db_index=True)
    metric_name = models.CharField(max_length=255)
    dimension_data = models.JSONField(null=True, blank=True)

    value = models.BigIntegerField()
