"""Dependency-free setup bootstrap. Never installs Bridge packages on Python 3.14."""
import argparse
import json
import os
import subprocess
import sys

PREFERRED = ('3.13', '3.12', '3.11')
PROBE = "import json,sys,struct,sysconfig; print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:2]),'bits':struct.calcsize('P')*8,'implementation':sys.implementation.name,'free_threaded':bool(sysconfig.get_config_var('Py_GIL_DISABLED'))}))"


def compatible(info):
    return (info.get('version') in ([3,13],[3,12],[3,11])
        and info.get('bits') == 64
        and info.get('implementation') == 'cpython'
        and not info.get('free_threaded',False))


def probe(command):
    env = dict(os.environ)
    # Interpreter selection must not silently trigger an installation.
    env.pop('PYLAUNCHER_ALLOW_INSTALL', None)
    output = subprocess.check_output(command + ['-c',PROBE],text=True,
        stderr=subprocess.PIPE,timeout=20,env=env)
    return json.loads(output)


def select_runtime(launcher='py', probe_fn=probe):
    for version in PREFERRED:
        try:
            info = probe_fn([launcher,'-'+version])
            if compatible(info) and info['version'] == [int(p) for p in version.split('.')]:
                return info
        except (OSError,subprocess.SubprocessError,ValueError,KeyError):
            continue
    raise RuntimeError('Python 3.13, 3.12 oder 3.11 (CPython, 64-bit, Standard-Build) fehlt. Installiere Python 3.13 zusaetzlich zu 3.14. Danach Setup.ps1 erneut starten.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--launcher',default='py')
    args=parser.parse_args()
    try:
        if args.check:
            info=probe([sys.executable])
            if not compatible(info):
                raise RuntimeError('Die vorhandene Umgebung nutzt keine unterstuetzte Python-Version.')
        else:
            info=select_runtime(args.launcher)
        print(json.dumps(info,ensure_ascii=True))
        return 0
    except (RuntimeError,OSError,subprocess.SubprocessError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
