"""Explicit structural benchmark; demo does not certify a real profile."""
import os
from pathlib import Path
import pytest
from .test_postgres_integration import postgres_app
from evaluation.performance import run_benchmark

pytestmark = pytest.mark.skipif(os.getenv('QUALITY_PERFORMANCE') != 'true', reason='explicit performance target required')


def test_ten_thousand_active_chunks_twenty_scopes(postgres_app, tmp_path):
    target = Path(os.environ['QUALITY_PERFORMANCE_OUTPUT']) if os.getenv('QUALITY_PERFORMANCE_OUTPUT') else Path('/quality-results/performance-demo.json') if Path('/quality-results').is_dir() else tmp_path / 'performance-demo.json'
    report = run_benchmark(postgres_app, target)
    assert report['real_profile_gate'] == 'incomplete'
    assert report['dimensions'] == postgres_app.config['EMBEDDING_DIMENSIONS']
    assert report['semantic_release_passed'] is False
