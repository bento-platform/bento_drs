import pytest
import requests
import shutil
import signal
import subprocess as sp
import time

from .constants import S3_HOST, S3_PORT, S3_SERVER_URL

"""
Taken from aioboto3's unit tests: https://github.com/terricain/aioboto3/blob/main/tests/mock_server.py

This PyTest plugin provides the 's3_server' fixture, which starts/stops a mocked S3 server for tests.
"""

_proxy_bypass = {
    "http": None,
    "https": None,
}


def start_service(service_name, host, port):
    moto_svr_path = shutil.which("moto_server")
    args = [moto_svr_path, "-H", host, "-p", str(port)]
    process = sp.Popen(args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)  # shell=True
    url = "http://{host}:{port}".format(host=host, port=port)

    for i in range(0, 30):
        output = process.poll()
        if output is not None:
            print("moto_server exited status {0}".format(output))
            stdout, stderr = process.communicate()
            print("moto_server stdout: {0}".format(stdout))
            print("moto_server stderr: {0}".format(stderr))
            pytest.fail("Can not start service: {}".format(service_name))

        try:
            # we need to bypass the proxies due to monkeypatches
            requests.get(url, timeout=5, proxies=_proxy_bypass)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)
    else:
        stop_process(process)  # pytest.fail doesn't call stop_process
        pytest.fail("Can not start service: {}".format(service_name))

    return process


def stop_process(process):
    try:
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=20)
    except sp.TimeoutExpired:
        process.kill()
        outs, errors = process.communicate(timeout=20)
        exit_code = process.returncode
        msg = "Child process finished {} not in clean way: {} {}".format(exit_code, outs, errors)
        raise RuntimeError(msg)


@pytest.fixture
def s3_server():
    process = start_service("s3", S3_HOST, S3_PORT)
    yield S3_SERVER_URL
    stop_process(process)
