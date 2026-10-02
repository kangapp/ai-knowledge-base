import os
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parent.parent


def transfer_script():
    workflow = yaml.safe_load((ROOT / '.github/workflows/deploy.yml').read_text())
    step = next(
        step for step in workflow['jobs']['deploy']['steps']
        if step.get('name') == 'Transfer release image to VPS'
    )
    return step['run']


@pytest.mark.parametrize('failure', ['', 'pull', 'save', 'ssh'])
def test_image_transfer_preserves_stream_and_propagates_failures(tmp_path, failure):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    docker = bin_dir / 'docker'
    docker.write_text('''#!/bin/sh
if [ "$1" = "pull" ]; then
    [ "$FAILURE" != "pull" ] || exit 7
elif [ "$1" = "save" ]; then
    [ "$FAILURE" != "save" ] || exit 8
    printf 'release-image-fixture'
else
    exit 99
fi
''')
    ssh = bin_dir / 'ssh'
    ssh.write_text('''#!/usr/bin/env python3
import gzip, os, pathlib, stat, sys
args = sys.argv[1:]
key = pathlib.Path(args[args.index('-i') + 1])
assert stat.S_IMODE(key.stat().st_mode) == 0o600
assert key.read_text().strip() == 'test-private-key'
pathlib.Path(os.environ['KEY_LOG']).write_text(str(key))
data = sys.stdin.buffer.read()
if os.environ['FAILURE'] == 'ssh':
    sys.exit(9)
if os.environ['FAILURE'] != 'save':
    assert gzip.decompress(data) == b'release-image-fixture'
assert 'deployer@example.test' in args
assert 'docker load' in args[-1]
''')
    docker.chmod(0o755)
    ssh.chmod(0o755)
    key_log = tmp_path / 'key-path'
    env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}',
               TMPDIR=str(tmp_path), FAILURE=failure, KEY_LOG=str(key_log),
               DEPLOY_IMAGE='ghcr.io/example/app:commit',
               VPS_SSH_KEY='test-private-key', VPS_HOST='example.test', VPS_USER='deployer')
    result = subprocess.run(['bash', '-c', transfer_script()], env=env,
                            capture_output=True, text=True)
    assert (result.returncode == 0) == (failure == ''), result.stderr
    if failure == 'pull':
        assert not key_log.exists()
    else:
        assert not Path(key_log.read_text()).exists()
    assert 'test-private-key' not in result.stdout + result.stderr
