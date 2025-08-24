import urllib.request
import time
import json
import boto3
import os

cloudwatch = boto3.client("cloudwatch")
NAMESPACE = "WebsiteHealth"

def _http_get(url: str, timeout_sec: int = 10):
    """Perform HTTP GET and measure latency (ms)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Canary/1.0"})
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=timeout_sec)
    latency_ms = (time.time() - start) * 1000.0
    return resp.getcode(), latency_ms

def handler(event, context):
    # Load sites from the deployed asset
    sites_path = os.path.join(os.path.dirname(__file__), "sites.json")
    with open(sites_path, "r") as f:
        sites = json.load(f)

    results = []

    for url in sites:
        status_val = 0     # default: down
        latency_ms = 0.0   # default: no latency recorded

        try:
            code, latency = _http_get(url)
            latency_ms = latency
            status_val = 1 if code == 200 else 0
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            # leave status_val=0 and latency_ms=0.0

        # Always publish both metrics
        metric_data = [
            {
                "MetricName": "Availability",
                "Dimensions": [{"Name": "URL", "Value": url}],
                "Value": status_val,
                "Unit": "Count"
            },
            {
                "MetricName": "Latency",
                "Dimensions": [{"Name": "URL", "Value": url}],
                "Value": latency_ms,
                "Unit": "Milliseconds"
            }
        ]

        # Push metrics to CloudWatch
        cloudwatch.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data)

        results.append({"url": url, "status": status_val, "latency_ms": latency_ms})

    print("Run results:", results)
    return {"statusCode": 200, "body": results}
