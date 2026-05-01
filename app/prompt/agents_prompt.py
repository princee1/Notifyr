from textwrap import dedent
from app.classes.prompt import System

detail_map = {
        "concise": "Keep responses brief and high value.",
        "balanced": "Provide useful detail without unnecessary length.",
        "precise": "Be exact, careful, and technically accurate.",
        "comprehensive": "Be thorough and cover relevant nuance.",
    }
audience_map = {
        "general": "Assume a general audience.",
        "beginner": "Explain simply and define uncommon terms.",
        "intermediate": "Assume some prior knowledge.",
        "expert": "Use domain terminology efficiently.",
        "executive": "Focus on decisions, tradeoffs, and outcomes.",
    }

uncertainty_map = {
        "say_unknown": "If uncertain, clearly state uncertainty.",
        "best_effort": "If uncertain, provide the best answer and note assumptions.",
        "ask_clarifying_question": "If requirements are unclear, ask a clarifying question before proceeding.",
    }


def SYSTEM_PROMPT(cfg: System) -> str:
    lines = []

    # Identity
    lines.append(f"You are {cfg.persona}.")
    lines.append(f"Your primary task is: {cfg.task}.")
    lines.append(f"Maintain a {cfg.personality} tone.")

    lines.append(detail_map[cfg.detail])

    lines.append(audience_map[cfg.audience])
    lines.append(uncertainty_map[cfg.uncertainty_behavior])

    if cfg.instruction:
        lines.append(cfg.instruction.strip())

    return dedent("\n".join(f"- {line}" for line in lines)).strip()