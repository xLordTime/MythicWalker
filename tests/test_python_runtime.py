import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from python_runtime import compatible, select_runtime


def runtime(version,bits=64,free_threaded=False):
    return {'executable':'C:/Python/python.exe','version':version,'bits':bits,
        'implementation':'cpython','free_threaded':free_threaded}

class RuntimeTests(unittest.TestCase):
    def test_python314_is_not_compatible(self):
        self.assertFalse(compatible(runtime([3,14])))
        self.assertFalse(compatible(runtime([3,13],32)))
        self.assertFalse(compatible(runtime([3,13],free_threaded=True)))
        self.assertTrue(compatible(runtime([3,13])))

    def test_explicit_runtime_despite_default_python314(self):
        probes=[]
        def fake(command):
            probes.append(command)
            return runtime([3,13] if command[-1]=='-3.13' else [3,14])
        chosen=select_runtime(probe_fn=fake)
        self.assertEqual(chosen['version'],[3,13])
        self.assertEqual(probes,[['py','-3.13']])

    def test_fallback_to_existing_python312(self):
        def fake(command):
            if command[-1]=='-3.13':raise subprocess.CalledProcessError(1,command)
            return runtime([3,12])
        self.assertEqual(select_runtime(probe_fn=fake)['version'],[3,12])

    def test_no_supported_python_stops_before_install(self):
        with self.assertRaisesRegex(RuntimeError,'Installiere Python 3.13'):
            select_runtime(probe_fn=lambda command:runtime([3,14]))

    def test_environment_check_uses_actual_interpreter(self):
        helper=Path(__file__).resolve().parents[1]/'bridge'/'python_runtime.py'
        p=subprocess.run([sys.executable,str(helper),'--check'],text=True,capture_output=True)
        expected=sys.version_info[:2] in ((3,11),(3,12),(3,13))
        if expected:
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)['version'],list(sys.version_info[:2]))
        else:self.assertNotEqual(p.returncode,0)

if __name__=='__main__':unittest.main()
