import signal
from unittest.mock import patch
import pytest
from services.shutdown_controller import ShutdownController
pytestmark=pytest.mark.unit

def test_initial_state():
    c=ShutdownController(); assert not c.shutdown_requested and c.signal_number is None

def test_request_is_idempotent_and_keeps_first_signal():
    c=ShutdownController(); c.request_shutdown(signal.SIGTERM); c.request_shutdown(signal.SIGINT)
    assert c.shutdown_requested and c.signal_number==signal.SIGTERM and c.wait(0)

def test_programmatic_request_and_wait_without_timeout():
    c=ShutdownController()
    c.request_shutdown()
    assert c.shutdown_requested and c.signal_number is None and c.wait()

def test_handler_requests_shutdown():
    c=ShutdownController(); c._handle_signal(signal.SIGINT, None)
    assert c.shutdown_requested and c.signal_number==signal.SIGINT

@pytest.mark.parametrize("method", ["install_signal_handlers", "restore_signal_handlers"])
def test_signal_handler_operations_require_main_thread(method):
    c=ShutdownController()
    with patch("services.shutdown_controller.threading.current_thread", return_value=object()), \
         patch("services.shutdown_controller.threading.main_thread", return_value=object()):
        with pytest.raises(RuntimeError, match="main thread"):
            getattr(c, method)()

def test_install_and_restore_handlers():
    c=ShutdownController()
    with patch("services.shutdown_controller.signal.getsignal", side_effect=["old-term","old-int"]), patch("services.shutdown_controller.signal.signal") as set_signal:
        c.install_signal_handlers(); c.restore_signal_handlers()
    assert set_signal.call_count==4

def test_install_and_restore_are_idempotent():
    c=ShutdownController()
    with patch("services.shutdown_controller.signal.getsignal", return_value=None), \
         patch("services.shutdown_controller.signal.signal") as set_signal:
        c.install_signal_handlers()
        c.install_signal_handlers()
        c.restore_signal_handlers()
        c.restore_signal_handlers()
    assert set_signal.call_count == 4

def test_wait_rejects_negative_timeout():
    with pytest.raises(ValueError, match="zero or greater"):
        ShutdownController().wait(-1)
