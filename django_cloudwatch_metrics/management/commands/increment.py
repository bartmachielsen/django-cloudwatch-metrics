from django.core.management import BaseCommand
from django_cloudwatch_metrics import metrics


class Command(BaseCommand):
    help = 'Increment metrics to CloudWatch'

    def add_arguments(self, parser):
        parser.add_argument('metric_name', type=str)
        parser.add_argument('value', type=int)
        parser.add_argument('--dimension-name', type=str, default=None)
        parser.add_argument('--dimension-value', type=str, default=None)

    def handle(self, *args, **options):
        metrics.increment(
            metric_name=options['metric_name'],
            value=options['value'],
            dimension_name=options['dimension_name'],
            dimension_value=options['dimension_value'],
        )