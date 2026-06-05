from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKER_WORKFLOW_PATH = REPO_ROOT / '.github' / 'workflows' / 'docker.yaml'
PYPI_WORKFLOW_PATH = REPO_ROOT / '.github' / 'workflows' / 'release-pypi.yml'


def test_docker_workflow_builds_custom_ghcr_image_without_shared_runner_risk():
    workflow = DOCKER_WORKFLOW_PATH.read_text()

    assert 'runs-on: ubuntu-latest' in workflow
    assert 'ghcr.io/${GITHUB_REPOSITORY,,}' in workflow
    assert 'docker/build-push-action' in workflow

    for forbidden in (
        'self-hosted',
        'sudo',
        'systemctl',
        'docker image prune',
        'docker system prune',
        'docker-compose',
        'docker compose',
        '/var/lib/docker',
        'openwebui/open-webui',
        'DOCKERHUB_IMAGE',
    ):
        assert forbidden not in workflow


def test_pypi_release_workflow_does_not_run_on_main_pushes():
    workflow = PYPI_WORKFLOW_PATH.read_text()

    assert 'name: Release to PyPI' in workflow
    assert '- main' not in workflow
    assert 'pypi-release' in workflow
