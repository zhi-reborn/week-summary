from pydantic import ValidationError

from app.domain.facts import PersonExtraction


class InvalidStructuredResponse(ValueError):
    pass


def parse_person_extraction(raw: str) -> PersonExtraction:
    candidate = _json_candidate(raw)
    try:
        return PersonExtraction.model_validate_json(candidate)
    except (ValidationError, ValueError) as exc:
        raise InvalidStructuredResponse(f"invalid structured response: {exc}") from exc


def _json_candidate(raw: str) -> str:
    candidate = raw.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        first_newline = candidate.find("\n")
        candidate = candidate[first_newline + 1 : -3].strip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise InvalidStructuredResponse("invalid structured response: JSON object not found")
        candidate = candidate[start : end + 1]
    return candidate
