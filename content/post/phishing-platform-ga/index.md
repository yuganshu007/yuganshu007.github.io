---
title: Phishing Detection Platform Goes Live Across Fintech Clients
date: 2024-09-02
summary: Ensemble microservices now screening 1.8K requests/sec with automated drift monitoring and blue/green rollouts.
tags:
  - Security
  - Launches
categories:
  - News
image:
  caption: ''
  focal_point: 'center'
---

Our phishing detection stack is officially supporting customer traffic. Production highlights:

- **Autoscaling**: HPA policies tuned via KEDA metrics to elastically scale ingestion workers.
- **Reliability**: Canary judge flows with synthetic traffic caught two regressions before customer impact.
- **Visibility**: Grafana lenses combining feature drift, queue depths, and outcome review velocity.

Rolling updates now take under 12 minutes end-to-end with instant rollbacks.
