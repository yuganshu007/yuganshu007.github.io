---
title: ''
date: 2022-10-24
type: landing

design:
  spacing: '6rem'

sections:
  # Clean hero with profile photo and concise tagline
  - block: resume-biography-3
    id: about
    content:
      username: admin
      text: |-
        <div>
          <div style="font-size:1.1rem;color:#64748b;margin-bottom:.35rem">Software Development Engineer</div>
          <div style="font-size:1.2rem;color:#475569;line-height:1.6">
            MS Computer Science Graduate • Ex-Amazon SDE Intern • Full‑Stack Developer specializing in AI/ML, Cloud Technologies, and Scalable Systems
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1rem">
            <span class="skill-pill">Java</span>
            <span class="skill-pill">Python</span>
            <span class="skill-pill">React</span>
            <span class="skill-pill">AWS</span>
            <span class="skill-pill">Machine Learning</span>
            <span class="skill-pill">TypeScript</span>
            <span class="skill-pill">PostgreSQL</span>
          </div>
          <div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem">
            <a class="btn-primary" href="#contact">Get In Touch</a>
            <a class="btn-secondary" href="/uploads/Yuganshu_Jain_Resume.pdf">Download CV</a>
          </div>
        </div>
      button:
        text: ''
        url: ''
      headings:
        about: ''
        education: ''
        interests: ''
    design:
      avatar:
        size: xl
        shape: circle
  # Experience
  - block: markdown
    id: experience
    content:
      title: Professional Experience
      subtitle: Building scalable systems and innovative solutions at leading tech companies
      text: |-
        #### Amazon — Software Development Engineer Intern
        Amazon Ad's Sponsored Display Team · May 2025 – Aug 2025 · New York City, United States

        - Designed, tested and deployed ETL pipeline using a Java-based Amber orchestrator to run daily jobs on EMR (Apache Spark), processing 1,000+ hours/day of advertiser call transcripts.
        - Engineered Voice of Advertiser (VOA) analytics engine integrating Amazon Bedrock Claude 3.5 Haiku with advanced prompt engineering, achieving 97% extraction accuracy across 10 business insight categories.
        - Built data flow from Gong.io → Andes data lakes → enriched S3 insights, leveraging Spark RDD/DataFrame pipelines with Lambda, Athena, and Glue, achieving 100% data completeness with ~2s query latency.
        - Created an AI-powered recommendation system with interactive Streamlit dashboard and Bedrock-integrated chatbot serving 32,000+ Amazon Ads stakeholders, enabling 10x faster data-driven decisions.
        _Tech:_ Java, Python, AWS EMR, Apache Spark, Amazon Bedrock, S3, Lambda, Athena, Glue, Streamlit

        <img src="https://source.unsplash.com/1200x500/?newyork,office,technology" alt="Amazon internship work environment (illustrative)" style="width:100%;border-radius:12px;border:1px solid rgba(148,163,184,.35);margin:.75rem 0"/>

        #### Stony Brook University — Graduate Teaching Assistant & Research Content Writer
        Computer Science Department · Sept 2024 – Present · New York, United States

        - Lead TAs for CSE 371 (Logic in CS); provide advanced mentoring in Python and Java for 200+ students.
        - Conduct research on abortion laws (VAI lab, Prof. Klaus Mueller) with multi-dimensional policy datasets and visual analytics tools.
        - Synthesize research findings for CS department communications; published 25+ articles on Stony Brook CS News.
        _Tech:_ Python, Java, Research, Data Analysis, Visual Analytics, Technical Writing

        #### RSTech Softwares — Software Engineer (Full‑Stack)
        Nov 2021 – Aug 2024 · Noida, India

        - Optimized React/Next.js + PostgreSQL + Docker architecture achieving 52% reduction in page load times (caching, code‑splitting).
        - Architected microservices with REST APIs + Apache Cassandra to support 2,500+ concurrent users; reduced DB query time by 40%.
        - Built Amazon SES email‑reporting pipeline with routing & retries to resolve 344 issues and boost SLA adherence.
        - Led a 5‑engineer team with code reviews and mentoring, improving system reliability by 25%.
        _Tech:_ React.js, TypeScript, PostgreSQL, Next.js, Docker, Apache Cassandra, REST APIs, Amazon SES

        #### Infinity Haul — Software Development Engineer (Mobile)
        Apr 2021 – Nov 2021 · Delhi, India

        - Refactored Android modules in Java/Kotlin to reduce UI stalls and improve responsiveness by 40%.
        - Integrated Google Maps SDK with Firebase for real‑time tracking, lowering delivery times by 20%.
        - Built and maintained supervisor/manager/driver/owner modules in Android Studio; optimized SQLite and XML queries for 40% faster app loads.
        _Tech:_ Java, Kotlin, Android Studio, Google Maps SDK, Firebase, SQLite, XML
  # Projects
  - block: markdown
    id: projects
    content:
      title: Featured Projects
      subtitle: Cutting-edge solutions in AI/ML, cybersecurity, and scalable systems
      text: |-
        <div class="project-tabs">
          <button class="project-tab" data-project-tab="all">All</button>
          <button class="project-tab" data-project-tab="ai">AI/ML</button>
          <button class="project-tab" data-project-tab="security">Security Research</button>
          <button class="project-tab" data-project-tab="cyber">Cybersecurity</button>
          <button class="project-tab" data-project-tab="fullstack">Full‑Stack</button>
        </div>
        <div class="project-grid">
          <article class="project-card" data-project-cat="ai">
            <img src="https://source.unsplash.com/800x500/?ai,analytics,dashboard" alt="AI analytics dashboard (illustrative)"/>
            <div class="project-body">
              <h4 class="project-title">Voice of Advertiser (VOA) AI Analytics Engine</h4>
              <div class="project-meta">Python • Bedrock (Claude 3.5) • Spark • EMR • S3 • Lambda • Streamlit</div>
              <ul>
                <li>Processes 1,000+ hours/day of transcripts with 97% extraction accuracy.</li>
                <li>Reduced review time from 45 min → 2 min; 18% CPC improvement.</li>
              </ul>
            </div>
          </article>

          <article class="project-card" data-project-cat="security">
            <img src="https://source.unsplash.com/800x500/?binary,code,security" alt="Static & dynamic analysis (illustrative)"/>
            <div class="project-body">
              <h4 class="project-title">Memory Corruption Detection Framework</h4>
              <div class="project-meta">Python • C++ • ML • Static/Dynamic Analysis • AddressSanitizer</div>
              <ul>
                <li>Detects buffer/heap corruption and ROP chains across 10,000+ binaries.</li>
                <li>Coverage‑guided fuzzing and ASLR bypass detection with automated exploits.</li>
              </ul>
            </div>
          </article>

          <article class="project-card" data-project-cat="cyber">
            <img src="https://source.unsplash.com/800x500/?phishing,security,shield" alt="Phishing protection (illustrative)"/>
            <div class="project-body">
              <h4 class="project-title">Phishing Detection System</h4>
              <div class="project-meta">Python • XGBoost • DNN • scikit‑learn</div>
              <ul>
                <li>100K+ URL dataset; +20% detection accuracy; real‑time inference.</li>
                <li>Robustness via L1/L2 regularization and productionized scoring APIs.</li>
              </ul>
            </div>
          </article>

          <article class="project-card" data-project-cat="fullstack">
            <img src="https://source.unsplash.com/800x500/?ecommerce,shopping,technology" alt="E‑commerce platform (illustrative)"/>
            <div class="project-body">
              <h4 class="project-title">Scalable B2B E‑commerce Platform</h4>
              <div class="project-meta">React • TypeScript • PostgreSQL • Next.js • Docker • Cassandra</div>
              <ul>
                <li>Supports 2,500+ concurrent users; −30% transaction errors.</li>
                <li>−40% DB query times with microservices and data modeling.</li>
              </ul>
            </div>
          </article>
        </div>
  - block: markdown
    id: education
    content:
      title: Education
      subtitle: Stony Brook University · Jamia Hamdard
      text: |-
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
          <img src="/uploads/SBU.JPG" alt="Stony Brook University" style="height:72px;border-radius:12px;border:1px solid rgba(148,163,184,.35)"/>
          <div>
            <strong>Stony Brook University</strong> — M.S. Computer Science (2024–2026)<br/>
            Head Graduate Teaching Assistant (Logic in CS)
          </div>
        </div>
        
        <div style="height:12px"></div>
        
        <div><strong>Jamia Hamdard</strong> — B.Tech CSE (2017–2021), CGPA 9.6/10</div>
    design:
      columns: '1'
  # Publications
  - block: markdown
    id: publications
    content:
      title: Publications
      text: |-
        Selected articles and write‑ups available on request. I’ve also written 25+ articles for Stony Brook CS News.
    design:
      columns: '1'
  # Volunteering
  - block: markdown
    id: volunteering
    content:
      title: Volunteering — Rotaract Club of Visioners League
      text: |-
        Active Member (2020–Present) · Contributing to community development via technology education and social impact initiatives. Organized/led technical workshops and international seminars; reached 1000+ people across 10+ events.
    design:
      columns: '1'
  # Education (with SBU image only)
  - block: markdown
    id: education
    content:
      title: Education
      text: |-
        <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
          <img src="/uploads/SBU.JPG" alt="Stony Brook University" style="height:64px;border-radius:8px;border:1px solid rgba(148,163,184,.35)"/>
          <div>
            <strong>Stony Brook University</strong> — M.S. in Computer Science (Aug 2024 – May 2026), Graduate Teaching Assistant — Logic in Computer Science. Coursework: Data Science, Data Visualization, Computer Systems Security, Logic in CS, HCI.
          </div>
        </div>

        <div style="margin-top:.75rem">
          <strong>Jamia Hamdard</strong> — B.Tech in Computer Science & Engineering (Jul 2017 – May 2021), GPA 9.6/10. Coursework: Advanced DBMS, Distributed Systems, Advanced Computer Architecture, Advanced Java, OS Lab, Compiler Design Lab, Web Technology, Data Warehousing & Mining, Big Data.
        </div>
    design:
      columns: '1'

  # Contact
  - block: markdown
    id: contact
    content:
      title: Get In Touch
      text: |-
        Email: <a href="mailto:yuganshu.jain@stonybrook.edu">yuganshu.jain@stonybrook.edu</a><br/>
        Phone: <a href="tel:+19342559075">+1 (934) 255-9075</a><br/>
        Location: New York, United States<br/>

        <div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.75rem">
          <a class="btn-primary" href="/uploads/Yuganshu_Jain_Resume.pdf">Download CV</a>
          <a class="btn-secondary" target="_blank" rel="noopener" href="https://github.com/yuganshu007">GitHub</a>
          <a class="btn-secondary" target="_blank" rel="noopener" href="https://www.linkedin.com/in/yuganshu-jain-6047b6165/">LinkedIn</a>
        </div>
    design:
      columns: '1'
---
