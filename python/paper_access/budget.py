"""Conservative per-job cost reservations, serialized by SQLite."""

from decimal import Decimal

from .store import JobStore


def _money(amount: Decimal) -> None:
    if not amount.is_finite() or amount < 0:
        raise ValueError("cost must be finite and nonnegative")


class BudgetLedger:
    def __init__(self, store: JobStore):
        self.store = store

    @staticmethod
    def _total(db, job_id: str) -> Decimal:
        return sum((Decimal(row[0]) for row in db.execute(
            "SELECT COALESCE(actual_cost,upper_bound) FROM cost_reservations WHERE job_id=?", (job_id,))), Decimal("0"))

    def committed(self, job_id: str) -> Decimal:
        with self.store.connection() as db:
            return self._total(db, job_id)

    def reserve(self, job_id: str, request_id: str, upper_bound: Decimal) -> bool:
        _money(upper_bound)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM cost_reservations WHERE request_id=?", (request_id,)).fetchone()
            if old is not None:
                if old["job_id"] != job_id or Decimal(old["upper_bound"]) != upper_bound:
                    raise ValueError("request id already reserved with different job or cost")
                return True
            options = self.store.options(job_id)
            if self._total(db, job_id) + upper_bound > options.max_cost_usd:
                return False
            db.execute("INSERT INTO cost_reservations VALUES(?,?,?,?,?)", (request_id, job_id, str(upper_bound), None, "reserved"))
        return True

    def settle(self, request_id: str, actual_cost: Decimal) -> None:
        _money(actual_cost)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM cost_reservations WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                raise KeyError("unknown cost reservation")
            if row["actual_cost"] is not None:
                if Decimal(row["actual_cost"]) != actual_cost:
                    raise ValueError("settled cost cannot be changed")
                return
            if actual_cost > Decimal(row["upper_bound"]):
                raise ValueError("actual cost exceeds reserved upper bound; reconciliation required")
            db.execute("UPDATE cost_reservations SET actual_cost=?,status='settled' WHERE request_id=?", (str(actual_cost), request_id))
