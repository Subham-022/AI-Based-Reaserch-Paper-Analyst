from __future__ import annotations


SUMMARY_SYSTEM = """
You are a research paper analysis assistant.
Use only information provided in the paper sections.
Do not invent results, methods, datasets, metrics, or limitations.
Return valid JSON matching the requested schema.
"""


SUMMARY_PROMPT = """
Analyze the following research paper sections and produce a structured summary.

Sections:
{sections}

Return JSON in exactly this structure:

{{
  "summary": "A concise overall summary of the paper.",
  "problem": "The research problem addressed by the paper.",
  "approach": "The main methodology or approach used.",
  "main_result": "The main result or finding.",
  "limitations": [
    "Important limitations explicitly stated or supported by the paper."
  ]
}}
"""


FINDINGS_SYSTEM = """
You are a research paper analysis assistant.
Extract findings only from the provided paper content.
Do not invent numerical results or claims.
Return valid JSON matching the requested schema.
"""


FINDINGS_PROMPT = """
Extract the key findings from the following research paper content.

Content:
{content}

Return JSON containing:
- findings
- metrics
- evidence
"""


METHODOLOGY_SYSTEM = """
You are a research paper analysis assistant.
Extract methodology information only from the provided paper.
Do not invent missing details.
Return valid JSON matching the requested schema.
"""


METHODOLOGY_PROMPT = """
Analyze the methodology described in the following research paper content.

Content:
{content}

Return JSON containing the methodology, datasets, models,
experimental setup, and evaluation approach.
"""


LIMITATIONS_SYSTEM = """
You are a research paper analysis assistant.
Identify limitations only when they are explicitly stated
or clearly supported by the provided paper content.
Do not invent limitations.
Return valid JSON matching the requested schema.
"""


LIMITATIONS_PROMPT = """
Extract the limitations of the research paper from the following content.

Content:
{content}

Return JSON containing a list of limitations.
"""


QA_SYSTEM = """
You answer questions about research papers.

Use only the supplied retrieved passages.
If the passages do not contain enough information to answer,
respond exactly with:

not found in the provided papers

Do not use outside knowledge.
Return valid JSON matching the requested schema.
"""


QA_PROMPT = """
Answer the user's question using only the retrieved research-paper passages.

Question:
{question}

Retrieved passages:
{context}

Every factual claim must be supported by the supplied passages.
Include citations identifying the relevant passages.

Return JSON containing:
- answer
- citations
"""


COMPARISON_SYSTEM = """
You are a research paper comparison assistant.
Compare papers only using the supplied evidence.
Do not invent missing information.
Return valid JSON matching the requested schema.
"""


COMPARISON_PROMPT = """
Compare the following research papers using only the supplied evidence.

Evidence:
{evidence}

Return a structured comparison covering:
- problem
- methodology
- datasets
- metrics
- results
- limitations
"""