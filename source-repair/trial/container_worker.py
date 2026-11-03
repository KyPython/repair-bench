"""Trusted container-only worker. Never run candidate mode on the host."""
import errno
import json
import os
from pathlib import Path
import socket
import sys


def probe():
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    interfaces = sorted(p.name for p in Path('/sys/class/net').iterdir())
    env = dict(os.environ)
    expected = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/nonexistent',
                'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
    writes = {}
    for folder in ('/', '/input'):
        try:
            with open(folder + '/rb-benign-write-probe', 'x') as stream:
                stream.write('probe')
            writes[folder] = False
        except OSError as exc:
            writes[folder] = exc.errno == errno.EROFS
    with socket.socket() as sock:
        sock.settimeout(1)
        try:
            network_denied = sock.connect_ex(('1.1.1.1', 443)) != 0
        except OSError:
            network_denied = True
    observations = {'uid': os.getuid(), 'gid': os.getgid(), 'interfaces': interfaces,
                    'network_connect_denied': network_denied, 'write_denied_readonly': writes,
                    'cap_eff': status.get('CapEff', '').strip(),
                    'no_new_privs': status.get('NoNewPrivs', '').strip(),
                    'environment_exact': env == expected,
                    'docker_socket_absent': not Path('/var/run/docker.sock').exists(),
                    'memory_limit': Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                    'pids_limit': Path('/sys/fs/cgroup/pids.max').read_text().strip()}
    observations['isolated'] = (os.getuid() == os.getgid() == 65534 and interfaces == ['lo']
        and network_denied and all(writes.values()) and observations['cap_eff'] == '0000000000000000'
        and observations['no_new_privs'] == '1' and observations['environment_exact']
        and observations['docker_socket_absent'] and observations['memory_limit'] == '268435456'
        and observations['pids_limit'] == '32')
    print(json.dumps(observations, sort_keys=True))
    return 0 if observations['isolated'] else 1


def evaluate(branch):
    if not branch.replace('_', '').isalnum() or '/' in branch:
        raise ValueError('Invalid branch')
    sys.path.insert(0, '/input/trial')
    import run_trial
    import metamorphic
    protocol = run_trial.run(Path('/input') / branch, require_original=branch == 'upstream')
    supplemental = metamorphic.run(branch)
    print(json.dumps({'protocol': protocol, 'supplemental': supplemental}, sort_keys=True))
    return 0


if __name__ == '__main__':
    # A hard location guard avoids accidental host execution of this entrypoint.
    if Path(__file__).resolve() != Path('/input/trial/container_worker.py'):
        raise SystemExit('Worker runs only at the disposable container location')
    if len(sys.argv) != 3 or sys.argv[1] not in {'probe', 'evaluate'}:
        raise SystemExit('Expected probe/evaluate and branch')
    raise SystemExit(probe() if sys.argv[1] == 'probe' else evaluate(sys.argv[2]))
