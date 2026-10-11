import ctypes
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from adapter import WizAdapter
from windows_clients import wizard_windows


class Function:
    def __init__(self, call): self.call = call
    def __call__(self, *args): return self.call(*args)


class DiscoveryTests(unittest.TestCase):
    def test_pointer_sized_handles_exact_class_and_bounded_buffer(self):
        # Reproduce a handle that the upstream c_int callback truncates.
        expected = 0x1234567887654321 if ctypes.sizeof(ctypes.c_void_p) == 8 else 123
        names = {expected: 'Wizard Graphical Client', 9: 'Wizard101 Launcher', 10: 'Other'}
        def enum(callback, parameter):
            for handle in names: callback(handle, parameter)
            return True
        def classname(handle, buffer, size):
            self.assertEqual(size, len(buffer))
            self.assertGreater(size, len(names[handle]))
            buffer.value = names[handle]
            return len(buffer.value)
        api = SimpleNamespace(EnumWindows=Function(enum), GetClassNameW=Function(classname))
        self.assertEqual(wizard_windows(api, ctypes.CFUNCTYPE), [expected])

    def test_native_enumeration_failure_is_not_zero_clients(self):
        api = SimpleNamespace(EnumWindows=Function(lambda *args: False), GetClassNameW=Function(lambda *args: 0))
        with self.assertRaises(OSError): wizard_windows(api, ctypes.CFUNCTYPE)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows API smoke test')
    def test_real_windows_discovery(self):
        self.assertIsInstance(wizard_windows(), list)


class AttachTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, factory):
        adapter = WizAdapter.__new__(WizAdapter)
        adapter.handler = SimpleNamespace(clients=[], _managed_handles=[17], client_cls=factory, remove_dead_clients=lambda: [])
        adapter.discover_windows = lambda: [17]
        adapter.hooked = set(); adapter.freecam = set(); adapter.original_speeds = {}; adapter.errors = {}
        adapter.snapshot = AsyncMock(side_effect=lambda: [{'id': str(c.process_id)} for c in adapter.handler.clients])
        return adapter

    async def test_denied_attach_can_be_retried_without_stale_handle(self):
        attempts = []
        def factory(handle):
            attempts.append(handle)
            if len(attempts) == 1: raise PermissionError('access denied')
            return SimpleNamespace(window_handle=handle, process_id=42)
        adapter = self.adapter(factory)
        with self.assertRaisesRegex(RuntimeError, 'Spiel gefunden, Zugriff fehlgeschlagen'):
            await adapter.scan()
        self.assertEqual(adapter.handler._managed_handles, [])
        self.assertEqual(await adapter.scan(), [{'id': '42'}])
        await adapter.scan()
        self.assertEqual(attempts, [17, 17])
        self.assertEqual(adapter.handler._managed_handles, [17])

    async def test_one_denied_client_does_not_hide_other_clients(self):
        def factory(handle):
            if handle == 17: raise PermissionError('access denied')
            return SimpleNamespace(window_handle=handle, process_id=43)
        adapter = self.adapter(factory); adapter.discover_windows = lambda: [17, 18]
        self.assertEqual(await adapter.scan(), [{'id': '43'}])
        self.assertEqual(len(adapter.scan_errors), 1)
