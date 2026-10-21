"""Input and output guardrails for the Secure Enterprise Knowledge Assistant."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from app.config import settings

logger = logging.getLogger(__name__)

# Refusal templates (constants in one place)
REFUSAL_OUT_OF_SCOPE = "I can only help with questions about company documents."
REFUSAL_ACCESS = "This information is not available for your role."
REFUSAL_ATTACK = "This request cannot be processed."

# Allowed greetings that bypass retrieval with a friendly response
GREETING_PATTERNS = [
    r"^(hi|hello|hey|salam|assalam-o-alaikum|aoa|greetings)[\s!.]*$"
]

# Layer 1 Input Guardrail Patterns (Regex & Keywords in English & Roman Urdu)
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(your\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"forget\s+(all\s+)?(your\s+)?(instructions|rules|guidelines)",
    r"pichl[ea|i]\s+(instructions?|hidayat|rules?)\s+(bhool\s+jao|khatam\s+karo)",
    r"bypass\s+(system|guardrail|security|safety)",
    r"disregard\s+(all\s+)?(your\s+)?(previous|prior|above)?\s*(instructions|prompts|rules|guidelines)",
    r"you\s+are\s+now\s+in\s+dan\s+mode",
    r"new\s+system\s+instructions?:",
]

ROLE_IMPERSONATION_PATTERNS = [
    r"\bi\s+am\s+(the\s+)?(cfo|ceo|cto|admin|executive|hr\s+manager|manager|director)\b",
    r"\bmain\s+(cfo|ceo|cto|admin|hr|executive)\s+(hoon|hun)\b",
    r"\bmera\s+role\s+(cfo|admin|executive|hr)\s+hai\b",
    r"\bact\s+as\s+(the\s+)?(cfo|ceo|admin|executive)\b",
    r"\bas\s+the\s+(cfo|ceo|admin|executive)\b",
]

SYSTEM_PROMPT_REQUEST_PATTERNS = [
    r"(show|display|reveal|print|tell\s+me|give\s+me)\s+(your\s+)?(system\s+prompt|initial\s+prompt|system\s+instructions|instructions)",
    r"system\s+prompt\s+(kya\s+hai|dikhao|batao)",
    r"what\s+are\s+your\s+(internal\s+)?rules",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\b(write|compose|tell)\s+(me\s+)?(a\s+)?(funny\s+|hilarious\s+)?(poem|song|story|joke|essay)\b",
    r"\b(poem|shayari|latifa|joke)\s+(likho|sunao)\b",
    r"\b(tell\s+me\s+a\s+joke|funny\s+joke)\b",
    r"\bweather\s+(in|of|tomorrow|today)\b",
    r"\bmausam\s+kaisa\s+hai\b",
    r"\bwho\s+won\s+the\s+(football|cricket|match|game|world\s+cup)\b",
    r"\bmatch\s+kis\s+ne\s+jeeta\b",
]

# Cache of distinctive tokens per access level
_DISTINCTIVE_TOKENS: Dict[str, Set[str]] = {}


def build_distinctive_tokens() -> Dict[str, Set[str]]:
    """Build a mapping of distinctive tokens (4+ digit numbers, capitalized keywords)

    unique to specific access levels from document files.
    """
    global _DISTINCTIVE_TOKENS
    if _DISTINCTIVE_TOKENS:
        return _DISTINCTIVE_TOKENS

    docs_dir = Path(settings.DATA_DIR) / "nexora_docs"
    if not docs_dir.exists():
        docs_dir = Path("./data/nexora_docs")

    level_tokens: Dict[str, Set[str]] = {
        "public": set(),
        "hr": set(),
        "finance": set(),
        "engineering": set(),
        "executive": set()
    }

    # Extract tokens per level
    for file_path in docs_dir.rglob("*.md"):
        if file_path.name == "README.md":
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Extract access_level from frontmatter
        level = "public"
        for line in content.split("\n")[:10]:
            if line.startswith("access_level:"):
                level = line.split(":", 1)[1].strip().lower()
                break

        if level not in level_tokens:
            level_tokens[level] = set()

        # Extract 4+ digit numbers (e.g., salaries, budgets, ports)
        numbers = set(re.findall(r"\b\d{4,}\b", content))
        # Extract Capitalized project/codename identifiers
        names = set(re.findall(r"\b[A-Z][a-zA-Z0-9]{3,}\b", content))
        level_tokens[level].update(numbers | names)

    # Compute exclusivity: tokens that belong ONLY to that level
    distinctive: Dict[str, Set[str]] = {}
    for lvl, toks in level_tokens.items():
        other_tokens = set()
        for other_lvl, other_toks in level_tokens.items():
            if other_lvl != lvl:
                other_tokens.update(other_toks)
        distinctive[lvl] = toks - other_tokens

    _DISTINCTIVE_TOKENS = distinctive
    return _DISTINCTIVE_TOKENS


def log_guardrail_event(category: str, layer: str, user: str, question: str, reason: str):
    """Log every guardrail decision with metadata."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "category": category,
        "layer": layer,
        "reason": reason,
        "question": question[:100]
    }
    logger.warning("GUARDRAIL TRIGGERED: %s", json.dumps(event))


def is_greeting(question: str) -> bool:
    """Check if question is a simple greeting."""
    q = question.strip().lower()
    return any(re.match(pat, q) for pat in GREETING_PATTERNS)


def check_input(question: str, user: str = "anonymous") -> Dict[str, Any]:
    """Input guardrail evaluating queries against safety categories.

    Categories:
        - prompt_injection
        - role_impersonation
        - system_prompt_request
        - out_of_scope
        - ok

    Returns:
        Dict: {"allowed": bool, "category": str, "reason": str, "is_greeting": bool}
    """
    q_clean = question.strip()

    # 0. Check for harmless greetings
    if is_greeting(q_clean):
        return {
            "allowed": True,
            "category": "ok",
            "reason": "greeting",
            "is_greeting": True
        }

    # Layer 1: Deterministic rules (Regex and keywords for English and Roman Urdu)
    # Check Prompt Injection
    for pat in INJECTION_PATTERNS:
        if re.search(pat, q_clean, re.IGNORECASE):
            reason = f"Matched injection pattern: {pat}"
            log_guardrail_event("prompt_injection", "layer_1", user, q_clean, reason)
            return {"allowed": False, "category": "prompt_injection", "reason": reason, "is_greeting": False}

    # Check Role Impersonation
    for pat in ROLE_IMPERSONATION_PATTERNS:
        if re.search(pat, q_clean, re.IGNORECASE):
            reason = f"Matched role impersonation pattern: {pat}"
            log_guardrail_event("role_impersonation", "layer_1", user, q_clean, reason)
            return {"allowed": False, "category": "role_impersonation", "reason": reason, "is_greeting": False}

    # Check System Prompt Requests
    for pat in SYSTEM_PROMPT_REQUEST_PATTERNS:
        if re.search(pat, q_clean, re.IGNORECASE):
            reason = f"Matched system prompt request pattern: {pat}"
            log_guardrail_event("system_prompt_request", "layer_1", user, q_clean, reason)
            return {"allowed": False, "category": "system_prompt_request", "reason": reason, "is_greeting": False}

    # Check Out of Scope
    for pat in OUT_OF_SCOPE_PATTERNS:
        if re.search(pat, q_clean, re.IGNORECASE):
            reason = f"Matched out of scope pattern: {pat}"
            log_guardrail_event("out_of_scope", "layer_1", user, q_clean, reason)
            return {"allowed": False, "category": "out_of_scope", "reason": reason, "is_greeting": False}

    return {"allowed": True, "category": "ok", "reason": "Passed input checks", "is_greeting": False}


def check_output(answer_text: str, sources: List[Dict[str, Any]], allowed_levels: List[str], user: str = "anonymous") -> Dict[str, Any]:
    """Output guardrail:

    1. Ensures every cited doc_id belongs to an allowed access level.
    2. Defense in depth: Checks for distinctive tokens belonging to unauthorized levels.

    Returns:
        Dict: {"allowed": bool, "reason": str}
    """
    clean_allowed = {lvl.strip().lower() for lvl in allowed_levels}

    # Map of all known doc_ids to their access levels
    doc_levels = {
        "PUB-001": "public", "PUB-002": "public", "PUB-003": "public",
        "HR-001": "hr", "HR-002": "hr",
        "FIN-001": "finance", "FIN-002": "finance",
        "ENG-001": "engineering", "ENG-002": "engineering",
        "EXE-001": "executive"
    }

    # 1. Verify cited doc_ids
    for s in sources:
        doc_id = s.get("doc_id")
        level = doc_levels.get(doc_id)
        if level and level not in clean_allowed:
            reason = f"Cited source {doc_id} requires {level} level, which is not in allowed: {clean_allowed}"
            log_guardrail_event("data_leakage", "output_source_check", user, "", reason)
            return {"allowed": False, "reason": reason}

    # 2. Defense in depth: Check distinctive tokens of unauthorized levels
    distinctive_map = build_distinctive_tokens()
    all_levels = {"public", "hr", "finance", "engineering", "executive"}
    unauthorized_levels = all_levels - clean_allowed

    for unauth_lvl in unauthorized_levels:
        tokens_to_block = distinctive_map.get(unauth_lvl, set())
        for tok in tokens_to_block:
            if tok and re.search(rf"\b{re.escape(tok)}\b", answer_text):
                reason = f"Distinctive token '{tok}' from restricted level '{unauth_lvl}' detected in output"
                log_guardrail_event("data_leakage", "output_token_check", user, "", reason)
                return {"allowed": False, "reason": reason}

    return {"allowed": True, "reason": "Passed output checks"}
