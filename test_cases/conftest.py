import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-remote",
        action="store_true",
        default=False,
        help="Run tests that require access to remote authenticated Fiber nodes",
    )


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and hasattr(item, "_testcase"):
        item._testcase.did_pass = report.passed
