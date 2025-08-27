# DevOps Project – Website Monitoring with AWS CDK (Python)

This project is a complete **website monitoring system** built with **AWS CDK (Python)** and AWS managed services.

It deploys:

- **Crawler Lambda** → Checks multiple websites every 5 minutes
- **CloudWatch Metrics** → Availability & Latency (per URL)
- **CloudWatch Dashboard** → Visualizes health of monitored websites
- **CloudWatch Alarms** → Fires if a site goes down or latency is too high
- **SNS Notifications** → Sends alarm alerts by email
- **DynamoDB Logging** → Stores all alarm events for audit/history

---

## 🚀 Architecture

1. **Crawler Lambda** runs every 5 minutes via EventBridge.
2. It reads `lambda/sites.json` for URLs, measures status & latency.
3. Pushes metrics to CloudWatch under namespace **WebsiteHealth**.
4. CloudWatch alarms trigger when thresholds are breached.
5. Alarms notify via SNS → emails and trigger **AlarmLogger Lambda**.
6. AlarmLogger Lambda writes alarm events into a **DynamoDB table**.

---

## 📂 Project Structure

devops_canary/
├─ app.py
├─ requirements.txt
├─ cdk.json
├─ devops_canary/
│ ├─ init.py
│ └─ devops_canary_stack.py
└─ lambda/
  ├─ crawler.py
  ├─ alarm_logger.py
  └─ sites.json

---

## ⚙️ Deployment

### 1. Install dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
2. Bootstrap CDK (once per account/region)
cdk bootstrap
3. Deploy the stack
cdk deploy -c alertEmail=your@email.com
You will receive a confirmation email from AWS SNS – confirm it to start receiving alerts.
 
🧪 Testing & Verification
•	Run Lambda manually
AWS Console → Lambda → CrawlerLambda → Test → check output & logs
•	Metrics
CloudWatch → Metrics → WebsiteHealth → Availability/Latency
•	Dashboard
CloudWatch → Dashboards → WebsiteHealth
•	Alarms
CloudWatch → Alarms → AvailabilityAlarm & LatencyAlarm
•	Email notifications
Trigger alarm by adding a fake site in sites.json → redeploy → watch for ALARM email
•	DynamoDB logs
DynamoDB → WebsiteAlarmLog → Explore items → check alarm entries
 
🛑 Cleanup
To avoid AWS charges:
cdk destroy

<img width="468" height="659" alt="image" src="https://github.com/user-attachments/assets/c2b8e863-2f83-401e-8b70-6af4df614d2b" />
