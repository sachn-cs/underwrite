"""Property-based tests for core mechanism invariants using Hypothesis.

Item 68 from production roadmap.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given, settings

from ulu.core.mechanism import DelegatedUnderwriting
from ulu.errors import InfeasibleOperationError


class TestMechanismProperties:
    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
            ),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_credit_limit_non_negative(self, seeds) -> None:
        m = DelegatedUnderwriting()
        for user, budget in seeds:
            if user not in m.earned:
                m.add_seed(user, budget)
            limit = m.credit_limit(user)
            assert limit >= 0.0

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
            ),
            min_size=1,
            max_size=5,
        ),
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_total_principal_and_earned_non_negative(self, seeds, users) -> None:
        m = DelegatedUnderwriting()
        for user, budget in seeds:
            if user not in m.earned:
                m.add_seed(user, budget)
        for sponsor, child, amount in users:
            if sponsor in m.earned and child not in m.earned:
                try:
                    m.add_user(sponsor, child, amount)
                except InfeasibleOperationError:
                    pass
        total_principal = sum(m.principal.values())
        total_earned = sum(m.earned.values())
        assert total_principal >= 0.0
        assert total_earned >= 0.0

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5, alphabet="abcdefghijklmnopqrstuvwxyz"),
                st.floats(min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
            ),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_assert_invariants_after_seeds(self, seeds) -> None:
        m = DelegatedUnderwriting()
        for user, budget in seeds:
            if user not in m.earned:
                m.add_seed(user, budget)
        m.assert_invariants()
