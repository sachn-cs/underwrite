"""Unit tests for DLG invocation workflow."""

from __future__ import annotations

from ulu.npa.dlg_workflow import DlgInvocationWorkflow


class TestDlgInvocationWorkflow:
    def test_no_invoke_when_not_triggered(self) -> None:
        wf = DlgInvocationWorkflow()
        result = wf.evaluate_and_invoke("l1", 30, False, 10000.0, 500.0)
        assert result.invoked is False
        assert result.physical_recovery == 0.0
        assert result.bank_absorption == 500.0

    def test_invoke_at_120_days(self) -> None:
        wf = DlgInvocationWorkflow()
        result = wf.evaluate_and_invoke("l1", 119, False, 10000.0, 500.0)
        assert result.invoked is True
        assert result.physical_recovery == 500.0  # below 5% cap
        assert result.bank_absorption == 0.0
        assert result.event is not None
        assert result.event.event_type == "dlg_invocation"

    def test_capped_physical_recovery(self) -> None:
        wf = DlgInvocationWorkflow()
        result = wf.evaluate_and_invoke("l1", 119, False, 10000.0, 1000.0)
        assert result.invoked is True
        assert result.physical_recovery == 500.0  # 5% of 10000
        assert result.bank_absorption == 500.0

    def test_already_invoked_skipped(self) -> None:
        wf = DlgInvocationWorkflow()
        result = wf.evaluate_and_invoke("l1", 119, True, 10000.0, 500.0)
        assert result.invoked is False

    def test_can_originate_when_pool_sufficient(self) -> None:
        wf = DlgInvocationWorkflow()
        assert wf.can_originate(10000.0, 600.0) is True

    def test_can_originate_when_pool_insufficient(self) -> None:
        wf = DlgInvocationWorkflow()
        assert wf.can_originate(10000.0, 400.0) is False
