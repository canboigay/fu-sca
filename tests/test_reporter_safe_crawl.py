import json, tempfile, shutil
from pathlib import Path
from reporter import Reporter

class FakeProxy:
    def __init__(self):
        self._data = {
            'requests': [
                {'url': 'https://example.com/', 'resource_type': 'document'},
                {'url': 'https://example.com/api/data', 'resource_type': 'xhr'},
                {'url': 'https://cdn.example.org/lib.js', 'resource_type': 'script'},
            ],
            'responses': [
                {'url': 'https://example.com/', 'status': 200, 'headers': {'Server': 'nginx'}},
                {'url': 'https://example.com/api/data', 'status': 200, 'headers': {'Content-Type': 'application/json'}},
            ],
            'pairs': []
        }
    def get_network_data(self):
        return self._data


def test_generate_safe_crawl_summary_same_origin_only(tmp_path):
    out = tmp_path / 'out'
    r = Reporter('https://example.com', output_dir=str(out))
    fp = FakeProxy()
    r.generate_safe_crawl_summary(fp, forms_json='[]', include_third_party=False, export_csv=True)
    files = list((out / 'safe_crawl').glob('*.json'))
    assert files, 'expected a json artifact'
    with open(files[0], 'r') as f:
        data = json.load(f)
        assert 'https://example.com/' in data['visited_urls']
        assert all(u.startswith('https://example.com') for u in data['visited_urls'])
    csv_endpoints = list((out / 'safe_crawl').glob('*_endpoints.csv'))
    assert csv_endpoints, 'expected endpoints.csv'