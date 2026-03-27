> **Publishing this content in Atlassian Confluence**
>
> * **Page title:** Set the Confluence page title to *End-to-end agentic systems with self-improving behavior* (or your standard naming). Avoid adding a separate Heading 1 in the page body—Confluence uses the page title as the main heading.
> * **Paste / import:** Use your site’s Markdown import or paste (e.g. *Paste markdown* in the floating toolbar, or a Markdown macro) if available. Plain paste from this file may require minor cleanup in the visual editor.
> * **Diagrams (Mermaid):** Confluence does **not** render ` ```mermaid ` code blocks by default. Options: install a **Mermaid** (or diagram) app from Marketplace and use its **macro**—paste **only** the diagram text *inside* the macro, **without** the triple backticks or `mermaid` language tag. Alternatively, recreate diagrams in **draw.io**, **Excalidraw**, or Whimsical and embed images.
> * **Mermaid tips for macros:** Use simple double-quoted labels, avoid special characters in labels where possible, and keep one diagram per macro. Diagrams use **fill and stroke colors** (`style`, `classDef`, and `rect rgb(...)`) for readability; if your Confluence Mermaid app ignores custom styles, diagrams still render as plain boxes.
> * **Checklist:** The rollout section uses a **table** with ☐ so it works when Markdown task lists do not import.

## Overview

**Audience:** architects and engineers designing conversational or task agents that get better over time through memory and feedback—not through on-the-fly model fine-tuning.

**Scope:** a reference pattern for orchestration, multi-layer memory, retrieval, and persistence that you can map to your stack (any LLM framework, cloud, or datastore).


## What we mean by self-improving

In product terms, a **self-improving agent** is one whose **behavior and outputs improve across sessions** because the system **records, retrieves, and reuses** experience. Improvement comes from:

1. **Remembering** user and task context across sessions.
2. **Retrieving** the right context *before* planning or answering.
3. **Logging outcomes** (success, failure, retries, escalations).
4. **Promoting** repeated successes into reusable **playbooks** (procedures).
5. **Updating** durable **facts** and **preferences** when the signal is clear.

Model weights stay fixed; **memory and policy** change. This doc describes how to build that loop reliably.


## Reference architecture at a glance

| Concern | Typical building blocks |
|--------|-------------------------|
| **Session coherence** | Short-term store: last *N* turns, TTL (e.g. cache or key-value) |
| **Cross-session recall** | Long-term store: transcripts or summaries + optional **semantic** search |
| **Stable facts** | Semantic / profile store: facts, preferences, constraints |
| **Playbooks** | Procedural store: named workflows, steps, optional conditions |
| **Learning signal** | Episodic store: time-ordered events and outcomes |
| **Reasoning** | Orchestrator model + optional **specialist** agents or tools |
| **Governance** | What to write, when, and who can read it (PII, retention, audit) |

Technology examples in parentheses are **illustrative only**: Redis for session state, a document database for raw logs, a vector index for similarity search, etc. Swap in what your organization already runs.


## Core design principle: read before act, write after act

For each user turn, a stable pattern is:

1. **Assemble context** from memory (session + user-level stores).
2. **Run** the orchestrator (and tools or sub-agents).
3. **Persist** updates (session buffer, long-term turn, episodes, optional facts and procedures).

If you run the model **before** loading memory, you under-use prior learning. If you **never** persist after the turn, nothing compounds.

```mermaid
flowchart LR
    A["Assemble context from memory"] --> B["Orchestrator plans and acts"]
    B --> C["Persist session and durable updates"]
    C --> D["Return to user"]

    classDef context fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef orchestrate fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#4A148C
    classDef persist fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef output fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#006064

    class A context
    class B orchestrate
    class C persist
    class D output
```


## Layered memory: roles and responsibilities

### Short-term (session) memory

**Role:** keep the **current conversation** coherent—references to “earlier in this chat,” pending confirmations, slot filling.

**Characteristics:** scoped to a **session** (or thread), **bounded size**, **TTL**, fast reads/writes.

**Typical operations:** get recent messages for session *S*; append turn; clear session on logout or timeout.


### Long-term (transcript or summary) memory

**Role:** retain **what was said** across sessions so the agent is not starting from zero.

**Characteristics:** durable per **user** (or tenant + user); often a **document** per turn or per session; may include metadata (intent, entities, channel).

**Optional:** attach **embeddings** and a **vector index** so retrieval is by **meaning** (“what did we discuss about budgets?”) not only keywords.


### Semantic memory (facts and preferences)

**Role:** store **concise, stable** statements: preferences, profile facts, domain rules the product should consistently honor.

**Characteristics:** usually **user-scoped**; **searchable** (vector or structured); **updated** when the user corrects you or when policy changes.

**Typical operations:** add or upsert fact; search facts given current query; list or prune stale facts.


### Procedural memory (playbooks)

**Role:** store **how** to do recurring tasks: ordered steps, checklists, escalation paths.

**Characteristics:** **named** procedures; optional **conditions** (“when ticket is P1”); versioned or timestamped if governance matters.

**Typical operations:** save procedure; list procedures for user; fetch by name; inject into prompt when relevant.


### Episodic memory (what happened)

**Role:** **event log** for analytics and learning: tool failures, retries, human handoffs, successful resolutions.

**Characteristics:** **append-mostly**; rich **metadata** (latency, error code, SKU, region); filterable by time and event type.

**Use:** drive dashboards, trigger “promote to procedure,” and detect regressions after releases.


## How the layers fit together (conceptual)

```mermaid
flowchart TB
    subgraph session["Current session"]
        ST["Short-term: recent dialogue"]
    end

    subgraph durable["Durable, user-scoped"]
        LT["Long-term: searchable history"]
        SM["Semantic: facts and preferences"]
        PR["Procedural: playbooks"]
        EP["Episodic: outcomes timeline"]
    end

    ST --> Orch["Orchestrator"]
    LT --> Orch
    SM --> Orch
    PR --> Orch
    EP --> Orch

    Orch --> ST
    Orch --> LT
    Orch --> EP
    Orch -.-> SM
    Orch -.-> PR

    style session fill:#E1F5FE,stroke:#0277BD,stroke-width:2px
    style durable fill:#F5F5F5,stroke:#616161,stroke-width:2px
    style ST fill:#B3E5FC,stroke:#0277BD,stroke-width:2px,color:#01579B
    style LT fill:#FCE4EC,stroke:#AD1457,stroke-width:2px,color:#880E4F
    style SM fill:#DCEDC8,stroke:#558B2F,stroke-width:2px,color:#33691E
    style PR fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px,color:#4527A0
    style EP fill:#FFECB3,stroke:#F9A825,stroke-width:2px,color:#FF6F00
    style Orch fill:#E1BEE7,stroke:#7B1FA2,stroke-width:3px,color:#4A148C
```

Solid arrows: common every-turn read/write paths. Dotted arrows: **promotional** or **conditional** writes (not every message should become a fact or a new procedure).


## Orchestration: one front door, optional specialists

A practical pattern for complex products:

* A single **orchestrator** faces the user (classification, safety, tone, delegation).
* **Specialist** agents or **tools** handle domains (billing, inventory, HR policy) with **structured outputs** where possible.
* Sub-agents **do not** bypass the orchestrator to the user unless your product explicitly allows it.

**Routing:** define **intents** (or a small policy model) and **delegation rules**. Keep specialist prompts narrow; keep orchestrator instructions explicit about when to delegate and when to answer from **injected context** (e.g. “saved playbooks” section in the prompt).

```mermaid
flowchart TB
    U["User input"] --> CA["Context assembly: session, history, facts, playbooks"]
    CA --> O["Orchestrator"]
    O -->|domain A| S1["Specialist or tool A"]
    O -->|domain B| S2["Specialist or tool B"]
    O -->|save playbook| S3["Buffered write intent for after turn"]
    O -->|general| O
    S1 --> O
    S2 --> O
    S3 --> O
    O --> R["User-facing response"]
    S3 -.-> PM["Procedural store after turn completes"]

    style U fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    style CA fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style O fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px,color:#4A148C
    style S1 fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#263238
    style S2 fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#263238
    style S3 fill:#FFF8E1,stroke:#FF8F00,stroke-width:2px,color:#E65100
    style R fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#006064
    style PM fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px,color:#4527A0
```


## One turn, end to end (sequence)

```mermaid
sequenceDiagram
    participant User
    participant Gateway as Application layer
    participant ST as Session memory
    participant LT as Long-term memory
    participant SM as Semantic memory
    participant PR as Procedural memory
    participant EP as Episodic memory
    participant Orch as Orchestrator model

    rect rgb(227, 242, 253)
        User->>Gateway: message + session identifier
    end

    rect rgb(225, 245, 254)
        Gateway->>ST: load recent turns
        ST-->>Gateway: session context
    end

    rect rgb(245, 245, 245)
        Gateway->>LT: retrieve relevant past interactions optional
        LT-->>Gateway: ranked snippets
        Gateway->>SM: retrieve relevant facts optional
        SM-->>Gateway: facts
        Gateway->>PR: list or fetch playbooks optional
        PR-->>Gateway: procedures
        Gateway->>EP: recent events optional
        EP-->>Gateway: timeline
    end

    rect rgb(243, 229, 245)
        Gateway->>Orch: single prompt with delimited context blocks
        Orch-->>Gateway: reply and tool calls
    end

    rect rgb(255, 243, 224)
        Gateway->>ST: update session buffer
        Gateway->>LT: persist turn optional
        Gateway->>EP: append outcome event
        Note over Gateway: Facts and new playbooks written when policy allows
    end

    rect rgb(224, 247, 250)
        Gateway-->>User: response
    end
```


## Self-improvement loop (behavioral)

```mermaid
flowchart LR
    A["Retrieve all relevant memory"] --> B["Plan and execute"]
    B --> C["Outcome known"]
    C -->|success| D["Episode: success"]
    C -->|failure| E["Episode: failure and reason"]
    D --> F["Worth promoting"]
    E --> F
    F -->|durable fact| G["Semantic update"]
    F -->|repeatable workflow| H["Procedural create or update"]
    F -->|no| I["Stop or transcript only"]
    G --> I
    H --> I

    style A fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    style B fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#4A148C
    style C fill:#FFF9C4,stroke:#F9A825,stroke-width:2px,color:#F57F17
    style D fill:#C8E6C9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style E fill:#FFCDD2,stroke:#C62828,stroke-width:2px,color:#B71C1C
    style F fill:#FFE0B2,stroke:#EF6C00,stroke-width:2px,color:#E65100
    style G fill:#DCEDC8,stroke:#558B2F,stroke-width:2px,color:#33691E
    style H fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px,color:#4527A0
    style I fill:#ECEFF1,stroke:#546E7A,stroke-width:2px,color:#37474F
```


## Writes after the turn: what usually happens

```mermaid
flowchart TB
    T["Assistant turn complete"] --> W1["Refresh session buffer"]
    T --> W2["Append long-term record or summary"]
    T --> W3["Append episodic event"]
    T --> W4["Update semantic facts if extractor confident"]
    T --> W5["Create or update playbook if criteria met"]

    W1 --> Done["Next turn"]
    W2 --> Done
    W3 --> Done
    W4 --> Done
    W5 --> Done

    style T fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#4A148C
    style W1 fill:#B3E5FC,stroke:#0277BD,stroke-width:2px,color:#01579B
    style W2 fill:#F8BBD0,stroke:#AD1457,stroke-width:2px,color:#880E4F
    style W3 fill:#FFECB3,stroke:#F9A825,stroke-width:2px,color:#FF6F00
    style W4 fill:#C5E1A5,stroke:#689F38,stroke-width:2px,color:#33691E
    style W5 fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px,color:#4527A0
    style Done fill:#E0F7FA,stroke:#00838F,stroke-width:3px,color:#006064
```

Not every product needs all five every time; define **triggers** (e.g. only promote procedures after *k* similar successes).


## Short-term memory: component view

```mermaid
flowchart LR
    subgraph App["Application"]
        API[Chat or task API]
        MW[Memory coordinator]
    end

    subgraph Session["Session layer"]
        Store[Session store abstraction]
        Backing[(Fast store e.g. cache KV)]
    end

    API -->|get / save / clear| MW
    MW --> Store
    Store --> Backing

    style App fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style Session fill:#E1F5FE,stroke:#0277BD,stroke-width:2px
    style API fill:#C8E6C9,stroke:#388E3C,stroke-width:2px,color:#1B5E20
    style MW fill:#A5D6A7,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style Store fill:#B3E5FC,stroke:#0288D1,stroke-width:2px,color:#01579B
    style Backing fill:#81D4FA,stroke:#0277BD,stroke-width:2px,color:#01579B
```


## Long-term memory with optional semantic retrieval

Many teams store **raw documents** in a database and **search embeddings** in a vector index (same or separate system).

```mermaid
flowchart LR
    subgraph App["Application"]
        API2[Chat or task API]
        MW2[Memory coordinator]
    end

    subgraph LT["Long-term layer"]
        Logic[Read write coordinator]
        Docs[(Document store)]
        Vec[Embedding and vector search]
    end

    API2 --> MW2
    MW2 -->|save retrieve| Logic
    Logic --> Docs
    Logic --> Vec
    Vec --> Docs

    style App fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style LT fill:#FCE4EC,stroke:#AD1457,stroke-width:2px
    style API2 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px,color:#1B5E20
    style MW2 fill:#A5D6A7,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style Logic fill:#F8BBD0,stroke:#C2185B,stroke-width:2px,color:#880E4F
    style Docs fill:#F48FB1,stroke:#AD1457,stroke-width:2px,color:#880E4F
    style Vec fill:#F06292,stroke:#880E4F,stroke-width:2px,color:#4A148C
```

**Save path (conceptual):** normalize text → embed → write document and vector pointer → index for search.

**Retrieve path:** embed query → similarity search → return top-*k* with scores → optional score threshold.

**Design choice:** some libraries can call an LLM during ingest to **infer** atomic memories. That is powerful but adds cost, latency, and failure modes. Many production systems instead use **explicit extraction** (your own prompt or rules) into semantic and procedural stores.


## Combined flow: load memory, run orchestrator, save

```mermaid
flowchart TB
    Req["Incoming request"] --> Load["Load session and user memory"]
    Load --> Run["Run orchestrator"]
    Run --> Save["Persist session and durable memory"]
    Save --> Resp["Respond"]

    subgraph Memory["Memory systems"]
        direction TB
        Sess["Session"]
        Long["Long-term"]
    end

    Load --> Sess
    Load --> Long
    Save --> Sess
    Save --> Long

    style Req fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    style Load fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style Run fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px,color:#4A148C
    style Save fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#BF360C
    style Resp fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#006064
    style Memory fill:#FAFAFA,stroke:#757575,stroke-width:2px
    style Sess fill:#B3E5FC,stroke:#0277BD,stroke-width:2px,color:#01579B
    style Long fill:#F8BBD0,stroke:#AD1457,stroke-width:2px,color:#880E4F
```


## Retrieval order before generation (recommended default)

1. **Session** context (immediate thread).
2. **Semantic** facts and hard constraints (policies, preferences).
3. **Procedural** playbooks if the task type matches.
4. **Long-term** history by semantic or hybrid search.
5. **Episodic** signals if you optimize for risk avoidance or repeat-incident handling.

Then **compose** one structured prompt (clear delimiters, cite source of each block). Avoid dumping unbounded text; **cap tokens** per block and total.


## Domain examples (how layers apply)

### Transaction or payments agent

* **Session:** amounts, recipients, pending MFA.
* **Long-term:** prior disputes and resolutions.
* **Episodic:** declines, limits, fraud flags, reference IDs.
* **Semantic:** default funding source, jurisdiction rules.
* **Procedural:** “verify high-value transfer” checklist.

**Improvement:** repeated failure reasons become **precheck steps** in the playbook; user corrections update **semantic** defaults.

### Support or triage agent

* **Semantic:** entitlements, known outages.
* **Procedural:** runbooks by symptom.
* **Episodic:** resolution paths that worked.
* **Long-term:** full ticket-style history when allowed.

**Improvement:** successful paths become **named runbooks**; noisy escalations become **routing rules**.

### Personal productivity agent

* **Semantic:** hours, style, goals.
* **Long-term:** commitments mentioned earlier.
* **Episodic:** follow-through over time.
* **Procedural:** weekly review, morning plan.

**Improvement:** if long plans are ignored, shorten default plan **procedure** or update **preference** facts.

```mermaid
flowchart TD
    Start["User goal e.g. payment or task"] --> Load["Load facts limits policies"]
    Load --> PB["Matching playbook"]
    PB -->|yes| Follow["Execute steps with checks"]
    PB -->|no| Reason["Reason with tools and policy"]
    Follow --> Check["Guardrails and validation"]
    Reason --> Check
    Check -->|blocked| Log1["Record episode blocked"]
    Check -->|ok| Exec["Execute side effect"]
    Exec --> Log2["Record episode success"]
    Log1 --> Out["Explain to user"]
    Log2 --> Out
    Log2 --> Learn["Optionally promote repeated success to playbook"]

    style Start fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    style Load fill:#DCEDC8,stroke:#558B2F,stroke-width:2px,color:#33691E
    style PB fill:#D1C4E9,stroke:#5E35B1,stroke-width:2px,color:#4527A0
    style Follow fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#263238
    style Reason fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#263238
    style Check fill:#FFF9C4,stroke:#F9A825,stroke-width:2px,color:#F57F17
    style Log1 fill:#FFCDD2,stroke:#C62828,stroke-width:2px,color:#B71C1C
    style Exec fill:#C8E6C9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    style Log2 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px,color:#1B5E20
    style Out fill:#E0F7FA,stroke:#00838F,stroke-width:2px,color:#006064
    style Learn fill:#FFE0B2,stroke:#EF6C00,stroke-width:2px,color:#E65100
```


## Data hygiene and safety

**Prefer storing**

* Durable preferences and policy facts.
* Summaries and structured outcomes, not full sensitive payloads unless required.
* Playbooks with explicit **when-to-use** conditions.

**Avoid**

* Duplicating the same narrative in four stores without purpose.
* Secrets in prompts or memory without vaulting and access control.
* Low-confidence extractions as immutable facts.

**Mnemonic**

* **Episodic** — what happened.
* **Semantic** — what is true (for the product).
* **Procedural** — how we do it.


## Governance and operations

* **Retention:** TTL for session; archival policy for long-term and episodes.
* **PII and consent:** what is stored, where, and for how long.
* **Quality:** periodic review of retrieved chunks and promoted playbooks.
* **Versioning:** when a procedure changes, keep **effective date** or version for audit.
* **Streaming APIs:** if you stream tokens to the client, ensure **the same context assembly** runs as in your non-streaming path unless you deliberately scope a lighter path.


## Metrics that indicate real improvement

* Task **success rate** and **time to resolution**.
* **Retries**, **tool errors**, and **user corrections** trending down.
* **Playbook reuse** and **semantic hit** quality (sampled review).
* **Escalation** rate for recurring issue classes.


## Rollout checklist (for your program)

Use Confluence task checkboxes on each row if your editor supports them; otherwise copy the ☐ column into a manual checklist.

| Step | Action | Done |
|------|--------|------|
| 1 | Define **memory tiers** and **owners** (who may read/write each). | ☐ |
| 2 | Implement **read path** (context assembly) with **budgets** per block. | ☐ |
| 3 | Implement **write path** after each turn (minimum: session + long-term or summary). | ☐ |
| 4 | Add **episodes** for measurable outcomes. | ☐ |
| 5 | Define **promotion rules** for facts and playbooks (thresholds, human review optional). | ☐ |
| 6 | Add **observability** (latency per store, cache hit rate, retrieval scores). | ☐ |
| 7 | Run **red-team / privacy** review on stored content. | ☐ |
| 8 | Document **orchestrator routing** and **specialist** boundaries for your team wiki. | ☐ |


## Summary

An end-to-end **self-improving agentic system** combines **orchestration**, **tools or specialists**, and **layered memory** with a strict **retrieve → act → persist** rhythm. Session memory keeps the thread coherent; long-term and semantic layers personalize and ground answers; episodic and procedural layers close the loop so **behavior improves with use**. Map the patterns above to your frameworks and data stores; the architecture stays the same even when the vendors change.

**Suggested Confluence page title:** *End-to-end agentic systems with self-improving behavior*
