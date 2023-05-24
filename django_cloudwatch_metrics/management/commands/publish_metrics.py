import logging
from datetime import datetime, timedelta

import boto3
import pytz
from django.conf import settings
from django.core.management import BaseCommand

from django_cloudwatch_metrics.models import MetricAggregation

logger = logging.getLogger(__name__)

NAMESPACE = getattr(settings, "CLOUDWATCH_METRICS_NAMESPACE", "DjangoCloudWatchMetrics")


def publish_metrics():
    logger.info("Publishing metrics to CloudWatch")
    cloudwatch = boto3.client("cloudwatch")
    metric_data = []

    metric_aggregations = MetricAggregation.objects.filter(datetime_period__lte=datetime.now(pytz.utc) - timedelta(minutes=1))

    for datetime_period, metric_name, value, dimension_name, dimension_value in metric_aggregations.values_list(
        "datetime_period", "metric_name", "value", "dimension_name", "dimension_value"
    ):
        logger.info(
            f"Publishing metric: {metric_name} " +
            (f"({dimension_name}:{dimension_value}) " if dimension_name and dimension_value else "") +
            f"with value: {value} at {datetime_period}"
        )
        metric_data.append(
            {
                "MetricName": metric_name,
                "Dimensions": [
                    {
                        "Name": dimension_name,
                        "Value": dimension_value
                    },
                ] if dimension_name and dimension_value else [],
                "Timestamp": datetime_period,
                "Value": value
            }
        )

    if metric_data:
        cloudwatch.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=metric_data
        )

    metric_aggregations.delete()
    logger.info("Published metrics to CloudWatch")


class Command(BaseCommand):
    help = 'Publishes metrics to CloudWatch'

    def handle(self, *args, **options):
        publish_metrics()