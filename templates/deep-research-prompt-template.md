---
title: "Шаблон универсального Deep Research промпта (для внешнего DR-инструмента)"
type: template
origin: anton
authored_by: human
date_established: 2026-06-14
theme: research-protocol
status: active
audience: both
tags: [шаблон, deep-research, alpha-protocol, research]
concept: "[[protocol-alpha-protocol-recall-plus-deep-research]]"
---

# Шаблон Deep Research промпта

> Единый источник истины для DR-промпта «Alpha Protocol». Claude Code эмитит его, подставив `{topic}` (и при наличии — `{objective}` / `{context}`), а Антон вставляет во внешний Deep Research инструмент (ChatGPT/Gemini/Perplexity Deep Research и т.п.). Канон протокола: [[protocol-alpha-protocol-recall-plus-deep-research]].

```
Conduct a deep research investigation on the following topic.

TOPIC:
{topic}

OBJECTIVE:
Find the best current practices, state-of-the-art approaches, failures, trade-offs, emerging trends, and implementation frameworks.

RESEARCH REQUIREMENTS:

1. Academic research
- papers
- meta analyses
- benchmarks

2. Industry practice
- startups
- unicorns
- leading companies
- open source projects

3. Competitive landscape
- direct competitors
- indirect competitors
- substitutes

4. Failure analysis
- failed attempts
- abandoned projects
- lessons learned

5. Emerging trends
- developments from the last 12 months
- frontier approaches

6. Implementation recommendations
- actionable framework
- roadmap
- priorities

OUTPUT FORMAT:

A. Executive Summary

B. Key Findings

C. Contradictions & Debates

D. Best Practices

E. Failure Modes

F. Strategic Recommendations

G. Action Plan

H. Sources
```

**Опционально** Claude Code добавляет в начало `CONTEXT:` блок с тем, что уже известно из RECALL (наши выводы, прошлые ошибки, открытые вопросы из Gap Analysis) — чтобы внешний DR не дублировал то, что мы уже знаем, а копал глубже.
