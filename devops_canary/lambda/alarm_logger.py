import json
import os
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def handler(event, context):
    # SNS event wrapper; multiple records possible
    # Each record contains an SNS message which (for CloudWatch alarms)
    # is a JSON string with "AlarmName", "NewStateValue", "Trigger", etc.
    for record in event.get("Records", []):
        try:
            msg = record["Sns"]["Message"]
            alarm = json.loads(msg)
        except Exception:
            # If non-JSON, still store raw
            alarm = {"RawMessage": record.get("Sns", {}).get("Message", "")}

        now_iso = datetime.now(timezone.utc).isoformat()

        item = {
            "AlarmName": str(alarm.get("AlarmName", "UnknownAlarm")),
            "Timestamp": now_iso,  # sort key
            "NewStateValue": str(alarm.get("NewStateValue", "UNKNOWN")),
            "NewStateReason": str(alarm.get("NewStateReason", ""))[:1000],
            "MetricName": str(alarm.get("Trigger", {}).get("MetricName", "Unknown")),
            "Namespace": str(alarm.get("Trigger", {}).get("Namespace", "")),
            "URL": _extract_url_from_dimensions(alarm.get("Trigger", {}).get("Dimensions", [])),
            "Raw": json.dumps(alarm)[:3500]  # keep a compact copy for debugging
        }

        table.put_item(Item=item)

    return {"statusCode": 200}

def _extract_url_from_dimensions(dims):
    for d in dims or []:
        if d.get("name") == "URL" or d.get("Name") == "URL":
            return d.get("value") or d.get("Value")
    return None
