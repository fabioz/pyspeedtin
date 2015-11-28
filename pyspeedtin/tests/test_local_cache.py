from pyspeedtin.local_cache import LocalCache

def test_local_cache(tmpdir):
    print(tmpdir)
    local_cache = LocalCache(str(tmpdir))
    local_cache.add('benchmark', {'name': 'bench1'})
    local_cache.add('benchmark', {'name': 'bench1'}) # Ignore this one (don't add duplicate data)
    local_cache.add('benchmark', {'name': 'bench2'})
    
    data_found = []
    with local_cache.load('benchmark') as benchmark_data:
        for handle in benchmark_data:
            assert not handle.has_rest_data()
            data_found.append(handle.data)
            handle.set_rest_data('something')
            assert handle.has_rest_data()
            
    assert data_found == [{'name': 'bench1'}, {'name': 'bench2'}]
    
    data_found = []
    rest_data_found = []
    with local_cache.load('benchmark') as benchmark_data:
        for handle in benchmark_data:
            assert handle.has_rest_data()
            data_found.append(handle.data)
            rest_data_found.append(handle.rest_data)

    assert data_found == [{'name': 'bench1'}, {'name': 'bench2'}]
    assert rest_data_found == ['something', 'something']
    
    data_found = []
    with local_cache.load('benchmark') as benchmark_data:
        for i, handle in enumerate(benchmark_data):
            if i == 0:
                handle.remove()
            data_found.append(handle.data)
    assert data_found == [{'name': 'bench1'}, {'name': 'bench2'}]

                
    data_found = []
    with local_cache.load('benchmark') as benchmark_data:
        for i, handle in enumerate(benchmark_data):
            data_found.append(handle.data)
    assert data_found == [{'name': 'bench2'}]
