---
title: Reddit Humor Detection & Funniness Prediction
subtitle: Ranking engagement through hybrid NLP
summary: Production ML workflow that classifies humor intent and predicts funniness scores with explainable insights for community managers.
date: 2025-03-04
featured: true
links:
  - icon: brands/github
    name: Repository
    url: https://github.com/yuganshu007/reddit-humor-detection
  - icon: link
    name: Poster
    url: https://yuganshu007.github.io/reddit-humor/
tags:
  - NLP
  - TensorFlow
  - MLOps
  - Data Visualization
categories:
  - Research Engineering
---

A full-stack NLP system that learns what makes Reddit content funny and how audiences respond.

- Curated and cleaned **1M+ joke submissions** with deduplication, sarcasm cues, and NSFW filters powered by spaCy custom components.
- Fused TF-IDF features, BERT embeddings, and handcrafted linguistic markers into a blended feature space, training Random Forest and Gradient models that hit **~86% accuracy**.
- Built a **regression pipeline (R² ≈ 0.87)** to score funniness, surfaced via Streamlit dashboards for subreddit moderators to plan campaigns.
- Automated experiment tracking with MLflow + DVC, bundling deployment scripts for batch scoring and A/B testing new content strategies.

The pipeline now drives editorial experimentation, enabling faster iteration on humor tone, scheduling, and personalization.

<!--more-->
