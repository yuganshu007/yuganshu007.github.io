---
title: Phishing Detection System
subtitle: Streaming threat intelligence in 80ms
summary: Ensemble ML microservices that flag malicious URLs in real time, deployed across Kubernetes with autoscaling and Redis-backed feature stores.
date: 2024-11-12
featured: true
links:
  - icon: brands/github
    name: Code
    url: https://github.com/yuganshu007
  - icon: link
    name: Demo Slides
    url: https://yuganshu007.github.io/phishing-detection-deck/
tags:
  - Systems Security
  - Machine Learning
  - MLOps
  - FastAPI
categories:
  - Security Engineering
---

A production-ready phishing detection platform combining classical ML ensembles with modern MLOps rigor.

- Trained **stacked ensemble models** (XGBoost, LightGBM, RF) on a 120K+ URL corpus, boosting true-positive recall by 21% while cutting false positives by 18%.
- Designed **feature store refresh pipelines** with Redis Streams + Celery workers to deliver features in under 30ms and keep models fresh hourly.
- Containerized FastAPI scoring services with **async inference + circuit breakers**, sustaining 1,800 requests/sec across a 3-node Kubernetes cluster.
- Instrumented OpenTelemetry traces and Grafana dashboards to surface drift, SLA burn rates, and shadow model comparisons in real time.

Result: analysts act on high-confidence signals in seconds, while the platform auto-retrains and redeploys without downtime.

<!--more-->
