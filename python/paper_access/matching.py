"""Conservative bibliographic matching; ambiguity is retained for review."""
from .models import PaperInput
from .validate import _author_present, _normalized


def _same_authors(left, right) -> bool:
    if not left or len(left) != len(right):
        return False
    assigned = {}
    def assign(index, seen):
        for target, author in enumerate(right):
            if target in seen or not (_author_present(left[index], author) and _author_present(author, left[index])):
                continue
            seen.add(target)
            if target not in assigned or assign(assigned[target], seen):
                assigned[target] = index
                return True
        return False
    return all(assign(index, set()) for index in range(len(left)))


def match_identity(input: PaperInput, records: list[PaperInput]) -> list[PaperInput]:
    if not input.title or not input.authors:
        return []
    return [record for record in records if _normalized(record.title) == _normalized(input.title)
            and (input.year is None or record.year == input.year)
            and _same_authors(input.authors, record.authors)]


def link_versions(left_id: str, right_id: str, evidence: dict, store) -> None:
    import json
    import time
    from .providers.base import persistent_uri
    if not left_id or not right_id or left_id == right_id or not evidence.get("method") or not persistent_uri(evidence.get("source")):
        raise ValueError("version relationship requires distinct identifiers and stable source evidence")
    with store.connection() as db:
        db.execute("INSERT OR IGNORE INTO version_relations VALUES(?,?,?,?)",
                   (left_id, right_id, json.dumps(evidence, sort_keys=True), time.time()))
