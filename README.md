# pyspeedtin

API to help in upload benchmark data to https://www.speedtin.com

Common use case:
    
    from pyspeedtin import PySpeedTinApi
    
    api = PySpeedTinApi()
    
    api.add_benchmark('create_10_users')
    api.add_benchmark('select_100_users')
    
    commit_id, branch, commit_date = api.git_commit_id_branch_and_date_from_path(__file__)
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

Note that each `add_benchmark()/add_measurement()` call will only create a local buffer to save
the contents, and only `api.commit()` will actually post the benchmarks/measurements.

Also, all the added benchmarks properly committed will have a local cache saved so that on
subsequent requests trying to add the same benchmark again will not do anything and when a
measurement is committed, it's changed by the id actually required by the REST API.