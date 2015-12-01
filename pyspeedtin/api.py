'''
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

Note that each add_benchmark()/add_measurement() call will only create a local buffer to save
the contents, and only api.commit() will actually post the benchmarks/measurements.

Also, all the added benchmarks properly committed will have a local cache saved so that on
subsequent requests trying to add the same benchmark again will not do anything and when a
measurement is committed, it's changed by the id actually required by the REST API.
'''
import datetime
import sys
import requests
import os
import subprocess
from pyspeedtin.local_cache import LocalCache


class PySpeedTinApi(object):
    '''
    This API caches things locally as much as possible and provides a way to create measurements
    based on the benchmark name (and not only the benchmark id, which is required by the REST API).

    It creates a local dict in the user settings dir to act as a local cache so that it doesn't
    need to query the server to get the benchmark id from the benchmark name.
    '''

    def __init__(self, authorization_key=None, project_id=None, clear_previous=False):
        '''
        :param str project_id:
            This is the id of the project (available in the Dashboard/Projects, next to the project
            name).

        :param str authorization_key:
            The key which is used to authorize with the backend (available in the Dashboard/User
            Settings).
        '''
        if authorization_key is None:
            try:
                authorization_key = os.environ['SPEEDTIN_AUTHORIZATION_KEY']
            except KeyError:
                raise AssertionError(
                    'The authorization key to commit the data was not passed nor is available in the SPEEDTIN_AUTHORIZATION_KEY environment variable.')
            
        if project_id is None:
            try:
                project_id = os.environ['SPEEDTIN_PROJECT_ID']
            except KeyError:
                raise AssertionError(
                    'The project_id to commit the data was not passed nor is available in the SPEEDTIN_PROJECT_ID environment variable.')
            
        self.authorization_key = authorization_key
        self.project_id = project_id
        


        self.base_url = 'https://www.speedtin.com'
        self.post = requests.post
        self.get = requests.get
        self._local_cache = LocalCache(os.path.join(self._data_dir(), str(project_id)))
        
        if clear_previous:
            self._local_cache.clear('measurement')
        else:
            # Print that we have remaining data from a previous call
            found = []
            with self._local_cache.load('measurement') as measurement_data:
                for handle in measurement_data:
                    found.append(handle.data)
            
            if found:
                sys.stderr.write('Warning: PySpeedTinApi:\nIn a previous call the following measurements where not properly saved:\n')
                for data in found:
                    sys.stderr.write(str(data))
                    sys.stderr.write('\n')
                sys.stderr.write('\nWhen committing, those values will also be saved...\n')
                sys.stderr.write(
                    'To prevent this from happening, pass "clear_previous=True" in the \n'
                    'PySpeedTinApi constructor or manually erase the contents at:\n%s\n\n' % (self._data_dir()))
        
    def date_to_str(self, date):
        return date.strftime('%Y-%m-%d %H:%M:%S.%f')

    def str_to_date(self, s):
        return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')

    def curr_date(self):
        return datetime.datetime.utcnow()

    def _data_dir(self):
        return os.path.join(os.path.expanduser('~'), '.speedtin')

    def commit(self):
        sys.stdout.write('Commit results...\n')
        assert not self.base_url.endswith('/'), 'The base url must not end with a slash.'
        self._commit_benchmarks()
        self._commit_measurements()

    def _commit_benchmarks(self):
        project_id = self.project_id
        authorization_key = self.authorization_key
        with self._local_cache.load('benchmark') as benchmark_data:
            for handle in benchmark_data:
                if not handle.has_rest_data():
                    data = handle.data
                    as_json = self.post_and_check_resut(
                        '%s/api/projects/%s/benchmarks' % (self.base_url, project_id), 
                        json=data, 
                        headers={'X-AuthToken': authorization_key},
                        msg='It was not possible to create the benchmark',
                        expected_status=201,
                    )
                    handle.set_rest_data(as_json)
                    sys.stdout.write('Saved benchmark: %s\n' % (as_json,))

    def _commit_measurements(self):
        project_id = self.project_id
        authorization_key = self.authorization_key

        with self._local_cache.load('benchmark') as benchmark_data:
            benchmark_name_to_id = {}
            for handle in benchmark_data:
                benchmark_name_to_id[int(handle.rest_data['id'])] = handle.data['name']

        with self._local_cache.load('measurement') as measurement_data:
            for handle in measurement_data:
                benchmark_id, json = handle.data

                try:
                    int(benchmark_id)
                except ValueError:
                    # The benchmark_id is actually the name of the benchmark, so, we have
                    # to get its id from the name.
                    try:
                        benchmark_id = benchmark_name_to_id[benchmark_id]
                    except KeyError:
                        # Ok, it's not there, try to get it from the REST API (and take the
                        # chance to update our local cache).
                        benchmarks_request = self.get('%s/api/projects/%s/benchmarks' % (
                            self.base_url,
                            project_id), headers={'X-AuthToken': authorization_key})
                        as_json = self.check_request_result(
                            benchmarks_request, 
                            'Unable to get the benchmarks from the server', 
                            expected_status=200, 
                        )

                        for benchmark in as_json:
                            if benchmark['name'] not in benchmark_name_to_id:
                                benchmark_name_to_id[benchmark['name']] = int(benchmark['id'])
                                self._local_cache.add(
                                    'benchmark', {'name': benchmark['name']}, benchmark)
                        try:
                            benchmark_id = benchmark_name_to_id[benchmark_id]
                        except KeyError:
                            raise ValueError(
                                'Unable to find benchmark with the name: %s' % (benchmark_id))

                as_json = self.post_and_check_resut(
                    '%s/api/projects/%s/benchmarks/%s/measurements' % (
                        self.base_url, project_id, benchmark_id),
                    json=json,
                    headers={'X-AuthToken': authorization_key},
                    msg='It was not possible to create the measurement',
                    expected_status=201,
                )
                sys.stdout.write('Saved measurement: %s\n' % (as_json,))
                handle.remove()
                
    def post_and_check_resut(self, url, json, headers, msg, expected_status):
        r = self.post(url, json=json, headers=headers, allow_redirects=False)
        as_json = self.check_request_result(r, msg+' Url: %s, Json: %s' % (url, json), expected_status)
        return as_json
        
    def check_request_result(self, r, msg, expected_status=201):
        if r.status_code != expected_status:
            raise RuntimeError('%s. Expected status: %s != %s Msg: %s' % (msg, expected_status, r.status_code, r.text,))
        
        as_json = r.json()
        
        if 'error' in as_json:
            raise RuntimeError('%s. Msg: %s' % (msg, r.text,))
        return as_json

    def add_benchmark(
        self,
        name,
    ):
        '''
        Creates a benchmark with the given name.

        :param str name:
            The name of the benchmark to be created.
        '''
        if len(name) > 50:
            raise ValueError('The maximum benchmark name size is 50 chars. The one passed has: %s chars' % (len(name),))
        self._local_cache.add('benchmark', {'name': name})

    def add_measurement(
        self,
        benchmark_id,
        value,
        version='dev',
        released=False,
        branch='',
        os=sys.platform,

        commit_id='',
        commit_date='',
        machine_name='',
        tag1='',
        tag2='',
    ):
        '''
        :param str benchmark_id:
            This is the id of the benchmark.

        :param float value:
            The value of the measurement. The actual meaning depends on the unit which is set in the 
            Benchmark (i.e.: it could be seconds, count, etc.)

        :param str version:
            A string which identifies the version.
            i.e.: 0.7.1, 2.7.9

        :param bool released:
            A boolean that identifies if this is a version which was released to your users.
            Automated regression reports from SpeedTin may give warnings for slower measurements
            considering the run against the latest released version.

        :param branch:
            This is the branch of the code used to do the measurement.
            i.e.: master, development, ...

        :param str os:
            The os in which the benchmark was run (Windows, Linux, MacOs) 

        :param commit_id:
            A hash for the commit for which this measurement was created.

        :param str commit_date:
            The date of the commit for this measurement.
            The date format is an utc date as: 2015-10-11 15:30:39.000

        :param str machine_name:
            The name of the machine in which this measurement was run.

        :param str tag1:
            Any value you feel it's important to tag this measurement.

        :param tag2:
            Any value you feel it's important to tag this measurement.
        '''
        json = {
            'value': value,
            'version': version,
            'released': released,
            'branch': branch,
            'os': os,
            'commit_id': commit_id,
            'commit_date': commit_date,
            'machine_name': machine_name,
            'tag1': tag1,
            'tag2': tag2,
        }
        self._local_cache.add(
            'measurement',
            (
                benchmark_id,
                json
            )
        )

    def run_and_get_output(self, *popenargs, **kwargs):
        '''
        Run command with arguments and return its output.
        '''
        process = subprocess.Popen(*popenargs, stdout=subprocess.PIPE, **kwargs)
        try:
            output, unused_err = process.communicate()
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if retcode:
            raise Exception('Process exited with value: %s. Args: %s. Output: %s' % (retcode, process.args, output))
        return output

    def git_commit_id_branch_and_date_from_path(self, repo_path):
        '''
        :param repo_path:

        :return tuple(str, str):
            Returns a tuple with the commit_id and the commit_date obtained from the given path
            (the repo_path must the one containing the .git folder or a sub-directory).
        '''
        if not os.path.exists(repo_path):
            raise OSError('The path: %s does not exist.' % (repo_path,))

        while not os.path.exists(os.path.join(repo_path, '.git')):
            initial = repo_path
            repo_path = os.path.dirname(repo_path)
            if initial == repo_path or not repo_path:
                raise OSError('The path: %s does not seem to be a git-managed path.' % (repo_path,))

        commit_id = self.run_and_get_output('git rev-parse HEAD'.split()).strip().decode('utf-8')
        branch = self.run_and_get_output(
            'git rev-parse --abbrev-ref HEAD'.split()).strip().decode('utf-8')
        commit_date = self.run_and_get_output(
            ['git', 'show', '-s', '--format=%ct', commit_id]).strip().decode('utf-8')

        commit_date = datetime.datetime.utcfromtimestamp(int(commit_date))
        return commit_id, branch, commit_date


if __name__ == '__main__':
    authorization_key = os.environ['SPEEDTIN_AUTHORIZATION_KEY']
    project_id = os.environ['SPEEDTIN_PROJECT_ID']
    api = PySpeedTinApi(authorization_key, project_id)
    api.base_url = 'http://127.0.0.1:8000'  # Test server

    api.add_benchmark('Bench1')
    api.add_benchmark('Bench2')

    commit_id, branch, commit_date = api.git_commit_id_branch_and_date_from_path(__file__)
    api.add_measurement(
        benchmark_id='Bench1',
        value=2,
        version='2.2',
        released=True,
        branch=branch,
        commit_id=commit_id,
        commit_date=commit_date,
    )
    api.add_measurement(
        benchmark_id='Bench2',
        value=1.8,
        version='2.2',
        released=True,
        branch=branch,
        commit_id=commit_id,
        commit_date=commit_date,
    )
