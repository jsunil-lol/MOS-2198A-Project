"""Join the AI steps: delay email -> facts -> calculations -> explanation.

The app passes in `build_analysis`, a function that takes the delay facts and
returns impact.py's DisruptionAnalysis (it holds the inventory, orders and
replacement offers). That keeps this file independent of impact.py.

If anything is flagged, we stop and hand the issues back so a person can fix
them. Calculations never run on facts that still need review.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import claude_client
from email_extraction import DelayFacts, extract_delay_facts
from explanation import Explanation, explain_recovery


@dataclass(frozen=True)
class PipelineResult:
    facts: DelayFacts
    analysis: Optional[object]
    explanation: Optional[Explanation]
    needs_review: bool
    issues: Tuple[str, ...]


def handle_delay_email(
    email_text: str,
    build_analysis: Callable[[DelayFacts], object],
    ask: Callable[..., str] = claude_client.ask_claude,
) -> PipelineResult:
    """Read the email, then (if the facts are clean) calculate and explain."""
    facts = extract_delay_facts(email_text, ask=ask)
    return explain_from_facts(facts, build_analysis, ask=ask)


def explain_from_facts(
    facts: DelayFacts,
    build_analysis: Callable[[DelayFacts], object],
    ask: Callable[..., str] = claude_client.ask_claude,
) -> PipelineResult:
    """Calculate and explain from facts, e.g. after a person corrected them."""
    if facts.needs_review:
        return PipelineResult(facts, None, None, True, facts.issues)

    try:
        analysis = build_analysis(facts)
    except Exception as error:  # impact.py raises ValueError on bad inputs
        return PipelineResult(
            facts, None, None, True, (f"The calculation failed: {error}",)
        )

    explanation = explain_recovery(analysis, ask=ask)
    return PipelineResult(
        facts, analysis, explanation, explanation.needs_review, explanation.issues
    )
