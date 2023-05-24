from django.db import models


class MetricAggregation(models.Model):
    """Metric Aggregation."""
    datetime_period = models.DateTimeField()
    metric_name = models.CharField(max_length=255)
    dimension_name = models.CharField(max_length=255, null=True)
    dimension_value = models.CharField(max_length=255, null=True)

    value = models.IntegerField()

    class Meta:
        unique_together = (
            ("datetime_period", "metric_name", "dimension_name", "dimension_value"),
        )
