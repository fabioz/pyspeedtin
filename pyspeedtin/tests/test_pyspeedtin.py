from pyspeedtin import PySpeedTinApi
import pytest
import json
from pyspeedtin.local_cache import json_dumps

class _Result(object):
    
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        
    def json(self):
        return json.loads(self.text)
    
class PostMock():
    
    def __call__(self, url, json, headers, **kwargs):
        if url == 'https://www.speedtin.com/api/projects/6546546/benchmarks' and json == {'name': 'create_10_users'}:
            return _Result(201, json_dumps({'id': 0, 'name': 'create_10_users'}))
        
        if url == 'https://www.speedtin.com/api/projects/6546546/benchmarks' and json == {'name': 'select_100_users'}:
            return _Result(201, json_dumps({'id': 1, 'name': 'select_100_users'}))
        
        if url == 'https://www.speedtin.com/api/projects/6546546/benchmarks/0/measurements':
            return _Result(201, json_dumps({'id': 0}))
        
        if url == 'https://www.speedtin.com/api/projects/6546546/benchmarks/1/measurements':
            return _Result(201, json_dumps({'id': 0}))
        
        raise AssertionError('Unexpected url: %s and json: %s' % (url, json))
        
class GetMock():
    
    def __call__(self, url, headers, **kwargs):
        if url == 'https://www.speedtin.com/api/projects/6546546/benchmarks':
            return _Result(200, json.dumps([{'id': 0, 'name': 'create_10_users'}, {'id': 1, 'name': 'select_100_users'}]))
        
        raise AssertionError('Unexpected url: %s' % (url,))

@pytest.fixture
def api():
    api = PySpeedTinApi('dummy_auth_key', 6546546)
    
    api.post = PostMock()
    api.get = GetMock()
    
    return api

def test_common_case(api):
    api.add_benchmark('create_10_users')
    api.add_benchmark('select_100_users')
    
    commit_id, branch, commit_date = 'commit_id', 'master', api.curr_date()
    api.add_measurement(
        benchmark_id='create_10_users', 
        value=1.8, 
        version='2.2', 
        released=True, 
        branch=branch, 
        commit_id=commit_id, 
        commit_date=commit_date, 
    )
    api.add_measurement(
        benchmark_id='select_100_users', 
        value=1.9, 
        version='2.2', 
        released=True, 
        branch=branch, 
        commit_id=commit_id, 
        commit_date=commit_date, 
    )
    
    api.commit()
