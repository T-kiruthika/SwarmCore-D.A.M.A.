# SwarmCore D.A.M.A: Agent-Aware Middleware for Legacy System Modernization

**Official Repository for Research Manuscript:**
*"AGENT-AWARE MIDDLEWARE FOR AUTONOMOUS LEGACY SYSTEM ENHANCEMENT: A DOMAIN-AGNOSTIC APPROACH"*
*(Currently Under Peer Review at Elsevier)*

## Project Context
This repository contains the functional sandbox and implementation artifacts for the research framework proposed in the manuscript above. This middleware utilizes a Shared Blackboard architecture to orchestrate multi-agent logic for legacy system remediation.

> **Transparency Notice:** This repository is maintained by the primary author of the referenced manuscript. The codebase serves as a functional demonstration of the proxy-based empirical validation described in Section 4 of the paper. 

> **AI Generation Notice:** Artificial Intelligence tools were utilized to assist in the generation and structural drafting of this codebase, adhering to modern AI-assisted research and development practices.

## Project Overview

Integrating modern generative AI into veteran enterprise infrastructures—such as COBOL-based financial mainframes, MUMPS healthcare ledgers, or industrial SCADA networks—carries an extreme risk of data corruption due to AI hallucinations. 

**SwarmCore D.A.M.A. (Domain-Agnostic Middleware Architecture)** is an experimental, event-driven multi-agent system built to act as a secure cognitive bridge for these aging systems. Because gaining direct testing access to live mission-critical mainframes is not feasible, **this repository utilizes structured Excel workbooks and SQLite databases as functional proxies**. While the sandbox runs on these proxy formats, the architectural logic is explicitly designed to scale to raw legacy storage environments.

This system is inherently **flow-driven**. If a target organizational process matches the asynchronous or synchronous event flows mapped by this middleware, the AI swarm can seamlessly adapt to manage it without requiring hardcoded rule rewrites.

---

## Critical Deployment Note: Domain Isolation

To maintain zero-hallucination data integrity, **each domain must be executed in strict isolation**. 

When running the sandbox, you must ensure that the institutional policy documents perfectly match the loaded proxy data. 
*   **Correct:** Running the Educational (`EDU`) compliance policy exclusively against the `EDU` database and Excel nodes.
*   **Correct:** Running the Information Technology (`IT`) SLA policy exclusively against `IT` network ledgers.
*   **FATAL:** Mixing `EDU` policies with `IT` data files in the same directory. 

Running multiple disparate domains simultaneously within the same active environment will poison the agents' context window and cause catastrophic routing confusion.

---

## Core Novelties & Features

*   **The 5-Agent Swarm:** Cognitive load is distributed across specialized personas: The *Concierge* (intent routing), *Data Engineer* (policy analysis), *Evaluator/Auditor* (mathematical policy enforcement), *Actuator* (sandbox execution), and the *Fixer* (error recovery).
*   **The Temporal Airlock:** An isolated execution boundary that entirely decouples generative AI reasoning from the physical database execution. The LLM generates an abstract JSON patch, which is mathematically proven by a deterministic Python validation layer before any state mutation is permitted.
*   **Autonomous Self-Healing:** Legacy systems are unpredictable. If the AI generates a syntactically flawed payload or encounters a database lock, the resulting Python traceback is immediately caught and routed to the *Fixer* agent, which autonomously repairs the logic and re-executes the transaction with zero downtime.
*   **Explainable AI (XAI) Telemetry:** Eliminates the "Black Box" problem. The system generates deterministic "Thought Logs" detailing exact policy citations, mathematical threshold proofs, and routing decisions, streaming them live to an Administrative Hub for complete algorithmic transparency.
*   **Shared Blackboard State:** Agents do not communicate linearly (which causes token bloat). Instead, they read and write to a centralized memory graph, radically reducing context window saturation.

---

## Omnichannel Control Centers & Cognitive Telemetry

SwarmCore D.A.M.A. completely decouples multi-agent reasoning logic from physical enterprise storage layers, manifesting across four distinct operational interfaces to coordinate real-time tracking, compliance enforcement, and human oversight.

### 1. Centralized Administrative Hub & Cognitive Stream
The master management terminal tracks the deployment state of active proxy ledger nodes while hosting a real-time **Cognitive Stream**. The `ORCHESTRATOR_EMISSION` engine flushes raw, step-by-step agentic logic maps—detailing policy criteria, math shield validations, and JSON diff patches—directly to system auditors for zero-"Black Box" operational transparency.

![System Validation Architecture](images/System%20Validation%20Architecture.png)

---

### 2. EduNexus Compliance Portal (Light-Domain UI)
A clean, light-themed administrative interface built for statutory compliance registry management and data mutation transactions within educational ecosystems. It maps structural leave parameters and generates immediate visual state changes upon a validated pass or an automated policy breach containment.

![Airlock Authorization State - Approved Request](images/Airlock%20Authorization%20State%20-%20Approved%20Request.png)

---

### 3. NexusData Maintenance Terminal (Dark-Domain UI)
An industrial, low-contrast dark-themed control center engineered explicitly for IT clusters, server uptime maintenance, and hardware tracking. The terminal executes secure state blocks, captures SLA warnings, and handles high-tier network overrides.

![SLA Threshold Breach Enforcement - Declined Request](images/SLA%20Threshold%20Breach%20Enforcement%20-%20Declined%20Request.png)

---

### 4. Telegram Human-in-the-Loop (HITL) Adjudication Node
An interactive mobile gateway that connects administrators directly to the inner multi-agent layer. When critical policy contradictions occur, the monitor bypasses suppression filters to pipe immediate HTML alerts to stakeholders, appending inline mobile layout commands (` Approve` / ` Decline`) to resolve pending state blocks instantly without web-console dependency.

![Mobile Chat HITL Incident Overrides](images/Mobile%20Chat%20HITL%20Incident%20Overrides.png)

---

## Flow-Driven Execution Lifecycle

The middleware operates via an Asynchronous Kafka-style queue, handling tasks across three distinct execution flows:

### 1. System Boot (Initialization Audit)
Triggered upon startup or via scheduled cron-jobs. The *Data Engineer* ingests and compresses raw PDF policies into strict mathematical constraints. The swarm scans the entire enterprise proxy ledger, identifies policy violations (e.g., SLA breaches, attendance shortages), applies a 30-day Anti-Spam lock to prevent alert fatigue, and notifies stakeholders.

### 2. Manual Update (Reactive Self-Healing)
If a human administrator manually modifies a raw cell in the legacy proxy ledger, the predictive monitor detects the timestamp shift. The swarm autonomously awakens, recalculates all derived macro-totals across the network, and silently goes back to sleep, maintaining continuous data integrity.

### 3. User Request & HITL (Transactional Pipeline)
Omnichannel ingestion from Web Portals or Telegram bots. The *Concierge* agent parses unstructured human intent, mapping it to specific legacy node targets. The *Evaluator* enforces temporal rules (rejecting retroactive tampering). Highly complex edge cases or requests requiring executive authority trigger a **Human-in-the-Loop (HITL)** escalation, pausing the autonomous swarm until a manager approves the transaction via their dashboard.

---

## Sandbox Installation & Setup

**1. Clone & Configure**
```bash
git clone https://github.com/T-kiruthika/SwarmCore-D.A.M.A..git
pip install -r requirements.txt
```
Populate the `.env.example` file with your respective Cloud API keys and rename it to `.env`.

**2. Generate Proxy Ledgers**
The system requires legacy data nodes to operate. Run the enterprise seeders to generate the proxy SQLite and Excel environments:
```bash
python edu_enterprise_seeder.py
python it_enterprise_seeder.py
```

**3. Boot the Ecosystem**
Launch the FastAPI Gateway, Telegram Listener, and Autonomous Monitor simultaneously:
```bash
python run_all.py
```

**4. CLI Testing**
For direct terminal interaction and debugging of the 3-Flow architecture:
```bash
python main.py
```
