import json
import re
from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

NAMESPACE = "WebsiteHealth"
LATENCY_THRESHOLD_MS = 1500  # adjust as needed

def _load_sites_list() -> list[str]:
    # Read sites.json at synth time so we can create per-URL alarms/widgets
    root = Path(__file__).resolve().parents[1]
    sites_path = root / "lambda" / "sites.json"
    if sites_path.exists():
        return json.loads(sites_path.read_text())
    return ["https://example.com"]

def _to_id_fragment(url: str) -> str:
    # Sanitize URL to be used in CDK logical IDs
    s = re.sub(r"[^A-Za-z0-9]", "", url)
    return s[:60] or "URL"

class DevopsCanaryStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sites = _load_sites_list()

        # 1) Lambda: crawler (publishes custom metrics)
        crawler_lambda = _lambda.Function(
            self, "CrawlerLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="crawler.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            description="Crawls websites and publishes Availability/Latency metrics",
        )

        # Allow PutMetricData to our crawler
        crawler_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"]  # PutMetricData has no resource-level restriction
            )
        )

        # 2) Schedule: every 5 minutes
        schedule_rule = events.Rule(
            self, "FiveMinuteSchedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            description="Invoke crawler Lambda every 5 minutes",
        )
        schedule_rule.add_target(targets.LambdaFunction(crawler_lambda))

        # 3) SNS Topics (separate by metric type for easy subscription filtering)
        availability_topic = sns.Topic(self, "AvailabilityTopic",
            display_name="Website Availability Alerts"
        )
        latency_topic = sns.Topic(self, "LatencyTopic",
            display_name="Website Latency Alerts"
        )

        # email subscription via context (`-c alertEmail=you@example.com`)
        email = self.node.try_get_context("alertEmail")
        if email:
            availability_topic.add_subscription(subs.EmailSubscription(email))
            latency_topic.add_subscription(subs.EmailSubscription(email))

        # 4) DynamoDB table for alarm logging
        alarm_table = dynamodb.Table(
            self, "WebsiteAlarmLog",
            partition_key=dynamodb.Attribute(name="AlarmName", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="Timestamp", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY  # change to RETAIN for production
        )

        # 5) Lambda: alarm logger (subscribed to both topics)
        alarm_logger = _lambda.Function(
            self, "AlarmLogger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="alarm_logger.handler",
            code=_lambda.Code.from_asset("lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={"TABLE_NAME": alarm_table.table_name},
            description="Writes CloudWatch alarm notifications into DynamoDB"
        )
        alarm_table.grant_write_data(alarm_logger)
        availability_topic.add_subscription(subs.LambdaSubscription(alarm_logger))
        latency_topic.add_subscription(subs.LambdaSubscription(alarm_logger))

        # 6) CloudWatch Dashboard
        dashboard = cloudwatch.Dashboard(
            self, "WebsiteHealthDashboard",
            dashboard_name="WebsiteHealth"
        )

        # Build per-URL metrics for nice multi-line charts
        avail_metrics = []
        latency_metrics = []
        for url in sites:
            m_av = cloudwatch.Metric(
                namespace=NAMESPACE,
                metric_name="Availability",
                dimensions_map={"URL": url},
                period=Duration.minutes(5),
                statistic="Average"
            )
            m_lt = cloudwatch.Metric(
                namespace=NAMESPACE,
                metric_name="Latency",
                dimensions_map={"URL": url},
                period=Duration.minutes(5),
                statistic="Average"
            )
            avail_metrics.append(m_av)
            latency_metrics.append(m_lt)

        if avail_metrics:
            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title="Website Availability (per URL)",
                    left=avail_metrics,
                    width=24
                )
            )
        if latency_metrics:
            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title="Website Latency (ms per URL)",
                    left=latency_metrics,
                    width=24
                )
            )

        # 7) Alarms per URL → send to appropriate SNS topic
        for url in sites:
            frag = _to_id_fragment(url)

            # Availability alarm: anything less than 1 in a period means DOWN
            av_metric = cloudwatch.Metric(
                namespace=NAMESPACE,
                metric_name="Availability",
                dimensions_map={"URL": url},
                period=Duration.minutes(5),
                statistic="Average"
            )
            av_alarm = cloudwatch.Alarm(
                self, f"AvailAlarm{frag}",
                metric=av_metric,
                threshold=0.99,  # treat 0 as breach
                evaluation_periods=1,
                datapoints_to_alarm=1,
                comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
                alarm_description=f"Availability below 1 for {url}"
            )
            
            av_alarm.add_alarm_action(cw_actions.SnsAction(availability_topic))
            av_alarm.add_ok_action(cw_actions.SnsAction(availability_topic))

            # Latency alarm
            lt_metric = cloudwatch.Metric(
                namespace=NAMESPACE,
                metric_name="Latency",
                dimensions_map={"URL": url},
                period=Duration.minutes(5),
                statistic="Average"
            )
            lt_alarm = cloudwatch.Alarm(
                self, f"LatencyAlarm{frag}",
                metric=lt_metric,
                threshold=LATENCY_THRESHOLD_MS,
                evaluation_periods=1,
                datapoints_to_alarm=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
                alarm_description=f"Latency above {LATENCY_THRESHOLD_MS} ms for {url}"
            )
            lt_alarm.add_alarm_action(cw_actions.SnsAction(latency_topic))
            lt_alarm.add_ok_action(cw_actions.SnsAction(latency_topic))

        # 8) Helpful outputs
        CfnOutput(self, "DashboardName", value=dashboard.dashboard_name)
        CfnOutput(self, "AvailabilityTopicArn", value=availability_topic.topic_arn)
        CfnOutput(self, "LatencyTopicArn", value=latency_topic.topic_arn)
        CfnOutput(self, "AlarmLogTableName", value=alarm_table.table_name)
