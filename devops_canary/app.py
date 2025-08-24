#!/usr/bin/env python3
import aws_cdk as cdk
from devops_canary.devops_canary_stack import DevopsCanaryStack

app = cdk.App()

# Optionally pin account/region:
# env = cdk.Environment(account="123456789012", region="ap-southeast-2")
# DevopsCanaryStack(app, "DevopsCanaryStack", env=env)

DevopsCanaryStack(app, "DevopsCanaryStack")
app.synth()
