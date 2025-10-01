---
title: ''
date: 2022-10-24
type: landing

design:
  spacing: '6rem'

sections:
  - block: resume-biography-3
    id: about
    content:
      username: admin
      text: |-
        ### Professional Summary
        I'm a distributed systems engineer obsessed with building production-grade data platforms, resilient microservices, and applied machine learning products that ship to stakeholders fast. I mix research-grade rigor with product intuition—whether it's orchestrating ETL pipelines over petabyte-scale telemetry or shipping AI copilots that unblock decision makers in minutes instead of hours.

        - Leads graduate TAs for Logic in CS at Stony Brook, shaping pedagogy and mentoring peers.
        - Translates research and prototypes into dashboards, APIs, and developer tooling that move business metrics.
        - Designs systems for reliability: automated rollback strategies, observability-first infrastructure, and graceful degradation everywhere.
      button:
        text: Download CV
        url: uploads/resume.pdf
      headings:
        about: ''
        education: ''
        interests: ''
    design:
      css_class: hbx-bg-gradient
      avatar:
        size: large
        shape: circle
  - block: markdown
    id: impact
    content:
      title: Impact Snapshot
      subtitle: Outcomes shipped across teams and platforms.
      text: |-
        <div class="glass-grid">
          <div class="glass-card">
            <div class="stat-value">1K+ hrs/day</div>
            <p class="stat-label">Transcripts processed with EMR/Spark ETL orchestrated in Java with zero-downtime retries.</p>
          </div>
          <div class="glass-card">
            <div class="stat-value">&lt;2s P95</div>
            <p class="stat-label">Latency for Bedrock-powered Voice of Advertiser copilot serving 500+ Ads stakeholders.</p>
          </div>
          <div class="glass-card">
            <div class="stat-value">10× faster</div>
            <p class="stat-label">Decision loops via ML observability dashboards and automated alerting pipelines.</p>
          </div>
          <div class="glass-card">
            <div class="stat-value">52% faster</div>
            <p class="stat-label">Page loads after Next.js micro-frontends, caching strategy, and perf budgets at RSTech Softwares.</p>
          </div>
          <div class="glass-card">
            <div class="stat-value">1.8K req/s</div>
            <p class="stat-label">Phishing detection microservices with FastAPI + Redis deployed across Kubernetes.</p>
          </div>
          <div class="glass-card">
            <div class="stat-value">25% ↑</div>
            <p class="stat-label">System reliability uplift by codifying security, observability, and incident runbooks across engineering pods.</p>
          </div>
        </div>
  - block: resume-experience
    id: experience
    content:
      title: Experience Highlights
      username: admin
      subtitle: Building high-leverage systems from scrappy startups to Amazon-scale.
    design:
      is_education_first: false
      date_format: 'Jan 2006'
  - block: collection
    id: projects
    content:
      title: Flagship Projects
      subtitle: Production work that blends distributed systems, ML, and product craft.
      filters:
        folders:
          - project
        featured_only: true
    design:
      view: article-grid
      columns: 3
      fill_image: false
      show_date: false
      show_read_time: false
      show_read_more: false
  
  - block: markdown
    id: community
    content:
      title: Community — Rotaract Club of Visioners League
      subtitle: Active Member (2020–Present) · India
      text: |-
        ### Creating Lasting Impact
        Through my involvement with the Rotaract Club of Visioners League, I've combined technical expertise with community service to create meaningful change. Technology is most powerful when it serves people; education unlocks potential.

        <div class="glass-grid">
          <div class="glass-card"><div class="stat-value">4+ Years</div><p class="stat-label">Dedicated service & continuous engagement</p></div>
          <div class="glass-card"><div class="stat-value">10+</div><p class="stat-label">Events organized — technical workshops & seminars</p></div>
          <div class="glass-card"><div class="stat-value">1000+</div><p class="stat-label">People reached as direct beneficiaries</p></div>
          <div class="glass-card"><div class="stat-value">2</div><p class="stat-label">International events led/co-led with global impact</p></div>
        </div>

        #### Key Contributions
        - Python & Possibilities Seminar (Organizer, 200+ participants): introduced Python fundamentals and real-world applications. Skills: event management, technical education, public speaking.
        - Competitive Programming Workshop (Co-organizer, 150+ developers): STL and dynamic programming curriculum. Skills: workshop planning, mentoring, curriculum design.
        - Deep Learning for COVID-19 Diagnosis (Key contributor, 500+ global attendees): coordinated international experts on AI for public health. Skills: international event management, healthcare tech, research coordination.
        - Smart Cities Global Scenario Seminar (Lead organizer, 300+ planners & technologists): knowledge exchange on urban technology. Skills: strategic planning, urban tech, international collaboration.
    design:
      columns: '1'
  - block: collection
    id: news
    content:
      title: Recent Updates
      subtitle: Wins, releases, and notes from the trenches.
      page_type: post
      count: 4
      filters:
        exclude_featured: false
    design:
      view: card
  - block: collection
    id: teaching
    content:
      title: Teaching & Mentorship
      filters:
        folders:
          - teaching
    design:
      view: article-grid
      columns: 2
  - block: markdown
    id: connect
    content:
      title: Let’s Build What’s Next
      text: |-
        I'm always up for conversations about large-scale data platforms, reliability engineering, or building product-oriented ML systems. If you're shipping something ambitious—or want to collaborate on research and teaching—drop a line.

        <div class="cta-buttons">
          <a class="cta-primary" href="mailto:yuganshu.jain@stonybrook.edu">Schedule a conversation</a>
          <a class="cta-secondary" href="https://www.linkedin.com/in/yuganshu-jain-6047b6165/" target="_blank" rel="noopener">Connect on LinkedIn</a>
        </div>
    design:
      columns: '1'
---
