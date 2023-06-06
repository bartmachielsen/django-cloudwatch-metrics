import logging
import time
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

    for datetime_period, metric_name, value, dimension_data in metric_aggregations.values_list(
        "datetime_period", "metric_name", "value", "dimension_data"
    ):
        logger.info(
            f"Publishing metric: {metric_name} " +
            (f"({dimension_data} " if dimension_data else "") +
            f"with value: {value} at {datetime_period}"
        )
        metric_data.append(
            {
                "MetricName": metric_name,
                "Dimensions": [
                    {
                        "Name": dimension_name,
                        "Value": dimension_value
                    }
                    for dimension_name, dimension_value in (dimension_data or {}).items()
                    if dimension_name and dimension_value
                ],
                "Timestamp": datetime_period,
                "Value": value
            }
        )

    if metric_data:
        # split in batches of max 1000
        for i in range(0, len(metric_data), 1000):
            cloudwatch.put_metric_data(
                Namespace=NAMESPACE,
                MetricData=metric_data[i:i+1000]
            )

    metric_aggregations.delete()
    logger.info("Published metrics to CloudWatch")


class Command(BaseCommand):
    help = 'Publishes metrics to CloudWatch'

    def add_arguments(self, parser):
        parser.add_argument(
            '--continuously',
            action='store_true',
            help='Continuously publish metrics to CloudWatch',
        )

    def handle(self, *args, **options):
        while True:
            publish_metrics()

            if not options['continuously']:
                break

            time.sleep(60)
