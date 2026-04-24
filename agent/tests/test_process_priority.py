"""Unit tests for _set_process_priority()."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import agent as _agent


class TestSetProcessPriority:

    def test_nice_called_with_below_normal_priority_class(self):
        mock_proc = MagicMock()
        with patch.object(_agent.psutil, "Process", return_value=mock_proc):
            _agent._set_process_priority()
        mock_proc.nice.assert_called_once_with(_agent.psutil.BELOW_NORMAL_PRIORITY_CLASS)

    def test_access_denied_is_handled_silently(self):
        FakeAccessDenied = type("AccessDenied", (Exception,), {})
        mock_proc = MagicMock()
        mock_proc.nice.side_effect = FakeAccessDenied()
        with patch.object(_agent.psutil, "Process", return_value=mock_proc), \
             patch.object(_agent.psutil, "AccessDenied", FakeAccessDenied):
            _agent._set_process_priority()
