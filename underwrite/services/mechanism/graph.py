"""Pure domain model for the delegation-based underwriting graph.

Encapsulates all graph state (seeds, parent-child relationships,
delegation edges, budgets, loans) and the operations that transform
it.  Has no dependencies on stores, event buses, or nano-service
infrastructure — making it testable in isolation.
"""

from __future__ import annotations

from typing import Any

from underwrite.__exceptions__ import InfeasibleOperationError, ProtocolError


class DelegationGraph:
    """Encapsulates the delegation graph state and its operations.

    Thread-safety is the caller's responsibility (use ``state_lock``
    in the owning service).
    """

    def __init__(self) -> None:
        self.seeds: set[str] = set()
        self.parent: dict[str, str] = {}
        self.children: dict[str, list[str]] = {}
        self.delegation: dict[tuple[str, str], float] = {}
        self.base_budget: dict[str, float] = {}
        self.earned: dict[str, float] = {}
        self.principal: dict[str, float] = {}
        self.loans: dict[str, list[dict[str, Any]]] = {}

    # -- query helpers --------------------------------------------------------

    def require_user(self, user: str) -> None:
        """Raise ProtocolError if *user* is not a known participant."""
        if user not in self.earned:
            raise ProtocolError(f"unknown user: {user}")

    def credit_limit(self, user: str) -> float:
        """Return the available credit limit for *user*."""
        budget = self.base_budget.get(user, 0.0) + self.earned.get(user, 0.0)
        if user in self.parent:
            sponsor = self.parent[user]
            budget = self.delegation.get(
                (sponsor, user), 0.0) + self.earned.get(user, 0.0)
        outgoing = sum(
            self.delegation.get((user, child), 0.0)
            for child in self.children.get(user, []))
        return budget - outgoing

    def total_credit_limit(self) -> float:
        """Return the sum of all users' credit limits."""
        return sum(self.credit_limit(u) for u in self.earned)

    def required_delegation(self, user: str, depth: int = 0) -> float:
        """Minimum delegation *user* must receive to remain solvent."""
        if depth > 50:
            raise ProtocolError(f"delegation chain too deep for {user}")
        if user in self.seeds:
            return 0.0
        child_req = sum(
            self.required_delegation(c, depth + 1)
            for c in self.children.get(user, []))
        return max(
            0.0,
            self.principal.get(user, 0.0) + child_req -
            self.earned.get(user, 0.0))

    def path_to_seed(self, user: str) -> list[str]:
        """Return the delegation path from *user* to a seed."""
        self.require_user(user)
        path: list[str] = [user]
        current: str = user
        seen: set[str] = {user}
        while current not in self.seeds:
            current = self.parent[current]
            if current in seen:
                raise ProtocolError(f"cycle detected for {user}")
            seen.add(current)
            path.append(current)
        path.reverse()
        return path

    # -- mutations -----------------------------------------------------------

    def add_seed(self, user: str, budget: float) -> None:
        """Register a new seed participant."""
        if user in self.earned:
            raise ProtocolError(f"user already exists: {user}")
        self.seeds.add(user)
        self.base_budget[user] = budget
        self.earned[user] = 0.0
        self.principal[user] = 0.0
        self.children[user] = []

    def add_user(self, sponsor: str, user: str, amount: float) -> None:
        """Add a new downstream participant sponsored by *sponsor*."""
        self.require_user(sponsor)
        if user in self.earned:
            raise ProtocolError(f"user already exists: {user}")
        if self.credit_limit(sponsor) < amount:
            raise InfeasibleOperationError("insufficient sponsor credit limit")
        self.parent[user] = sponsor
        self.children[user] = []
        self.children[sponsor].append(user)
        self.delegation[(sponsor, user)] = amount
        self.earned[user] = 0.0
        self.principal[user] = 0.0

    def repay(self, user: str, delta: float) -> None:
        """Increase *user*'s earned amount by *delta*."""
        self.require_user(user)
        self.earned[user] += delta

    def originate(
        self,
        borrower: str,
        principal: float,
        term: float,
        default_probability: float,
        protocol_rate: float,
        max_delegation_rate: float,
    ) -> dict[str, Any]:
        """Issue a loan to *borrower* and return the loan record."""
        self.require_user(borrower)
        if self.credit_limit(borrower) < principal:
            raise InfeasibleOperationError("principal exceeds credit limit")
        protocol_premium: float = protocol_rate * principal * term
        self.principal[borrower] = self.principal.get(borrower,
                                                      0.0) + principal
        loan: dict[str, Any] = {
            "borrower": borrower,
            "principal": principal,
            "term": term,
            "default_probability": default_probability,
            "protocol_rate": protocol_rate,
            "max_delegation_rate": max_delegation_rate,
            "protocol_premium": protocol_premium,
        }
        self.loans.setdefault(borrower, []).append(loan)
        return loan

    def default(self, borrower: str) -> None:
        """Process a default, propagating the loss up the delegation chain."""
        self.require_user(borrower)
        borrower_principal: float = self.principal.get(borrower, 0.0)
        if borrower_principal <= 0:
            raise InfeasibleOperationError("no outstanding principal")
        absorb: float = min(self.earned.get(borrower, 0.0), borrower_principal)
        self.earned[borrower] = self.earned.get(borrower, 0.0) - absorb
        loss: float = borrower_principal - absorb

        current: str = borrower
        while loss > 0 and current not in self.seeds:
            sponsor: str = self.parent[current]
            edge: tuple[str, str] = (sponsor, current)
            sponsor_absorb: float = min(self.earned.get(sponsor, 0.0), loss)
            self.earned[sponsor] = self.earned.get(sponsor,
                                                   0.0) - sponsor_absorb
            loss -= sponsor_absorb
            if loss > 0:
                current_edge_amount: float = self.delegation.get(edge, 0.0)
                if current_edge_amount < loss:
                    raise ProtocolError(
                        "insufficient delegation for default propagation")
                self.delegation[edge] = current_edge_amount - loss
            current = sponsor

        if loss > 0:
            if current not in self.seeds:
                raise ProtocolError("residual loss did not reach seed")
            seed_budget: float = self.base_budget.get(current, 0.0)
            if seed_budget < loss:
                raise ProtocolError("seed base budget overdraft")
            self.base_budget[current] = seed_budget - loss

        self.principal[borrower] = 0.0
        self.loans.pop(borrower, None)

    def revoke(self, sponsor: str, child: str, new_amount: float) -> None:
        """Change the delegation amount on the *sponsor* → *child* edge."""
        self.require_user(sponsor)
        self.require_user(child)
        if self.parent.get(child) != sponsor:
            raise ProtocolError("not the parent-child edge")
        needed: float = self.required_delegation(child)
        if new_amount < needed:
            raise InfeasibleOperationError(
                "revocation would make subtree insolvent")
        edge: tuple[str, str] = (sponsor, child)
        if edge not in self.delegation:
            raise ProtocolError("unknown delegation edge")
        old_amount: float = self.delegation[edge]
        if new_amount > old_amount:
            delta: float = new_amount - old_amount
            if self.credit_limit(sponsor) < delta:
                raise InfeasibleOperationError(
                    "insufficient credit limit to increase delegation")
        self.delegation[edge] = new_amount

    # -- persistence (snapshot / restore) ------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a deep-ish copy of all mutable state for rollback."""
        return {
            "seeds": set(self.seeds),
            "parent": dict(self.parent),
            "children": {k: list(v)
                         for k, v in self.children.items()},
            "delegation": dict(self.delegation),
            "base_budget": dict(self.base_budget),
            "earned": dict(self.earned),
            "principal": dict(self.principal),
            "loans": {k: list(v)
                      for k, v in self.loans.items()},
        }

    def restore(self, snap: dict[str, Any]) -> None:
        """Restore state from a snapshot (undo a mutation after persist failure)."""
        self.seeds = snap["seeds"]
        self.parent = snap["parent"]
        self.children = snap["children"]
        self.delegation = snap["delegation"]
        self.base_budget = snap["base_budget"]
        self.earned = snap["earned"]
        self.principal = snap["principal"]
        self.loans = snap["loans"]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for store persistence."""
        return {
            "seeds":
            sorted(self.seeds),
            "parent":
            dict(self.parent),
            "children": {k: list(v)
                         for k, v in self.children.items()},
            "delegation":
            {f"{s}->{c}": v
             for (s, c), v in self.delegation.items()},
            "base_budget":
            dict(self.base_budget),
            "earned":
            dict(self.earned),
            "principal":
            dict(self.principal),
            "loans": [
                loan for borrower_loans in self.loans.values()
                for loan in borrower_loans
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegationGraph:
        """Deserialize from a dict previously produced by ``to_dict()``."""
        g = cls()
        g.seeds = set(data.get("seeds", []))
        g.parent = dict(data.get("parent", {}))
        g.children = {k: list(v) for k, v in data.get("children", {}).items()}
        delegation_raw = data.get("delegation", {})
        g.delegation = {}
        for k, v in delegation_raw.items():
            s, c = k.split("->", 1)
            g.delegation[(s, c)] = v
        g.base_budget = dict(data.get("base_budget", {}))
        g.earned = dict(data.get("earned", {}))
        g.principal = dict(data.get("principal", {}))
        g.loans = {}
        for loan in data.get("loans", []):
            b = loan.get("borrower", "")
            g.loans.setdefault(b, []).append(loan)
        return g
