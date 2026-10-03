from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from paper_access.budget import BudgetLedger
from paper_access.models import JobOptions
from paper_access.store import JobStore


def ledger(tmp_path, limit="0"):
    store = JobStore(tmp_path / "db.sqlite")
    job = store.create([], [], JobOptions(tmp_path / "out", max_cost_usd=Decimal(limit)))
    return BudgetLedger(store), job


def test_zero_budget_blocks_charge_but_allows_free_request(tmp_path):
    budget, job = ledger(tmp_path)
    assert not budget.reserve(job, "paid", Decimal("0.01"))
    assert budget.reserve(job, "free", Decimal("0"))


def test_concurrent_reservations_cannot_overspend(tmp_path):
    budget, job = ledger(tmp_path, "0.03")
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda n: budget.reserve(job, str(n), Decimal("0.01")), range(20)))
    assert sum(outcomes) == 3
    assert budget.committed(job) == Decimal("0.03")


def test_unknown_request_result_keeps_reservation_across_restart(tmp_path):
    budget, job = ledger(tmp_path, "0.01")
    assert budget.reserve(job, "request1", Decimal("0.01"))
    reopened = BudgetLedger(JobStore(tmp_path / "db.sqlite"))
    assert not reopened.reserve(job, "request2", Decimal("0.01"))
    reopened.settle("request1", Decimal("0"))
    assert reopened.reserve(job, "request2", Decimal("0.01"))


def test_reservation_id_is_idempotent_and_cannot_change_owner_or_amount(tmp_path):
    budget, job = ledger(tmp_path, "0.02")
    assert budget.reserve(job, "same", Decimal("0.01"))
    assert budget.reserve(job, "same", Decimal("0.01"))
    assert budget.committed(job) == Decimal("0.01")
    with pytest.raises(ValueError):
        budget.reserve(job, "same", Decimal("0.02"))
    with pytest.raises(ValueError):
        budget.reserve("other-job", "same", Decimal("0.01"))


def test_settlement_is_idempotent_but_not_rewritable(tmp_path):
    budget, job = ledger(tmp_path, "1")
    budget.reserve(job, "one", Decimal("0.5"))
    budget.settle("one", Decimal("0.2"))
    budget.settle("one", Decimal("0.2"))
    with pytest.raises(ValueError):
        budget.settle("one", Decimal("0"))
    assert budget.committed(job) == Decimal("0.2")


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity"])
def test_invalid_money_is_rejected(tmp_path, amount):
    budget, job = ledger(tmp_path, "1")
    with pytest.raises(ValueError):
        budget.reserve(job, "one", Decimal(amount))
