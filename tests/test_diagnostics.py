from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
import diagnostics


class DiagnosticTests(unittest.TestCase):
    def test_exception_trace_and_rotated_export_hide_pairing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                path = diagnostics.start_logging(directory)
                diagnostics.hide_secret('very-private-pair-code')
                diagnostics.event('browser', url='https://example/#pair=very-private-pair-code')
                try: raise RuntimeError('failed very-private-pair-code')
                except RuntimeError: diagnostics.logger.exception('test.failure')
                diagnostics.logger.handlers[0].doRollover()
                diagnostics.event('after.rotation')
                report = diagnostics.bundle()
                combined = str(report)
                self.assertNotIn('very-private-pair-code', combined)
                self.assertIn('[REDACTED]', combined)
                self.assertIn('Traceback', combined)
                self.assertIn('after.rotation', combined)
                self.assertTrue(path.exists())
                self.assertEqual(len(report['logs']), 2)
            finally:
                for handler in list(diagnostics.logger.handlers):
                    diagnostics.logger.removeHandler(handler); handler.close()

    def test_export_tail_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                path = diagnostics.start_logging(directory)
                for handler in diagnostics.logger.handlers: handler.flush()
                path.write_bytes(b'x' * 300000)
                self.assertLessEqual(len(diagnostics.bundle()['logs'][0]['tail']), 160*1024)
            finally:
                for handler in list(diagnostics.logger.handlers):
                    diagnostics.logger.removeHandler(handler); handler.close()
