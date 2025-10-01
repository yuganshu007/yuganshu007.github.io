---
title: Voice of Advertiser AI Copilot
subtitle: Bedrock-assisted analyst in the loop
summary: Conversational analytics copilot that distills advertiser sentiment and budgets in minutes with sub-2s latency across 500+ stakeholders.
date: 2025-06-30
featured: true
links:
  - icon: link
    name: Bedrock Architecture
    url: https://www.amazon.jobs/
  - icon: link
    name: Product Brief
    url: https://yuganshu007.github.io/voa-brief/
tags:
  - AWS
  - Generative AI
  - Data Platforms
  - Product Engineering
categories:
  - Applied ML
---

Amazon Ads teams needed a way to interrogate voice-of-customer data without weeks of manual synthesis. I led the design and delivery of a Bedrock-powered copilot that compresses review time from 45 minutes to under 2 minutes.

- Orchestrated a **domain-adapted LLM workflow** over Bedrock, RAG pipelines, and curated semantic caches living in OpenSearch + S3.
- Implemented **distributed joins** across Spark and DynamoDB to stitch transcript metadata, campaign metrics, and historical intent labels, guaranteeing P95 latency under 2 seconds.
- Built a secure Streamlit UI with fine-grained IAM + SigV4 auth, giving 500+ Ads stakeholders instant access to structured Q&A, actionable prompts, and shareable insights.
- Shipped autoscaling guardrails, prompt analytics, and bias monitors to keep responses grounded in policy and evidence.

The copilot is now the primary interface for Ads leadership reviews, freeing analysts to focus on strategy instead of manual synthesis.

<!--more-->
