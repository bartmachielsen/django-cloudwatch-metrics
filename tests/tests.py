from django.test import TransactionTestCase

from django_cloudwatch_metrics import metrics
from django_cloudwatch_metrics.models import MetricAggregation


class TestPublishingMetrics(TransactionTestCase):
    """Test publishing metrics."""

    def setUp(self) -> None:
        pass

    def test_publishing_metrics(self):
        """Test publishing metrics."""
        for _ in range(1000):
            metrics.increment(
                metric_name="articles_published",
                value=1,
            )

        self.assertTrue(MetricAggregation.objects.filter(metric_name="articles_published").exists())
        self.assertEqual(MetricAggregation.objects.filter(metric_name="articles_published").first().value, 1000)