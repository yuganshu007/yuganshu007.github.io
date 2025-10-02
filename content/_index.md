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
        ##### AI/ML — Voice of Advertiser (VOA) AI Analytics Engine
        An analytics platform integrating Bedrock Claude 3.5 with advanced prompt engineering. Processes 1,000+ hours/day of advertiser call transcripts with 97% extraction accuracy across 10 business insight categories.
        - Served 32,000+ Amazon Ads stakeholders; reduced manual analysis from 45 minutes to 2 minutes per call; 10x faster decisions; 18% improvement in advertiser cost‑per‑click.
        _Tech:_ Python, Amazon Bedrock (Claude 3.5), Apache Spark, AWS EMR, S3, Lambda, Streamlit

        ##### Security Research — Memory Corruption Detection Framework
        Memory safety framework combining static analysis, dynamic fuzzing, and ML to detect buffer overflows, heap corruption, and ROP chains across 10,000+ binaries.
        - Coverage‑guided fuzzing, ASLR bypass detection, automated exploit scaffolds; integrations with AddressSanitizer and Valgrind.
        _Tech:_ Python, C++, Machine Learning, Static/Dynamic Analysis, AddressSanitizer

        ##### Cybersecurity — Phishing Detection System
        Ensemble ML system using Decision Trees, Random Forest, XGBoost, and DNNs trained on 100K+ URL samples. Achieved 20% improvement in phishing detection accuracy with real‑time inference.
        - Real‑time inference; L1/L2‑regularized XGBoost; productionized APIs.
        _Tech:_ Python, XGBoost, Deep Learning, Decision Trees, Random Forest, scikit‑learn

        ##### Full‑Stack — Scalable B2B E‑commerce Platform
        Full‑stack platform with payment gateways, QA pipelines, and RESTful orchestration. Reduced transaction errors by 30% and improved reliability by 25%.
        - Supports 2,500+ concurrent users; 40% faster DB queries; microservices on Apache Cassandra.
        _Tech:_ React.js, TypeScript, PostgreSQL, Next.js, Docker, Apache Cassandra, REST APIs
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
