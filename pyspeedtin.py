import datetime
import sys
import requests
import os
import subprocess


class PySpeedTinApi(object):

    def __init__(self, authorization_key, project_id):
        '''
        :param str project_id:
            This is the id of the project (available in the Dashboard/Projects, next to the project name).
            
        :param str authorization_key:
            The key which is used to authorize with the backend (available in the Dashboard/User Settings).
        '''
        self.authorization_key = authorization_key
        self.project_id = project_id
        self.data_to_commit = []
        self.created_benchmarks = {}
        self.base_url = 'https://www.speedtin.com'
        
    def date_to_str(self, date):
        return date.strftime('%Y-%m-%d %H:%M:%S.%f')

    def str_to_date(self, s):
        return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')

    def curr_date(self):
        return datetime.datetime.utcnow()
    
    def commit(self):
        pass
        
    def create_benchmark(
        self,
        name,
        ):
        '''
        Creates a benchmark with the given name.
        
        :param str name:
            The name of the benchmark to be created.
        '''
        r = requests.post('%s/dashboard/api/projects/%s/benchmarks' % (self.base_url,self.project_id), data={
            'name': name})
        if r.status_code != 201:
            raise AssertionError('It was not possible to create the measurement. Msg: %s' % (r.text,))
        return r.json()
        
    def create_measurement(
        self,
        benchmark_id,
        value,
        version='dev',
        released=False,
        branch='master',
        os=sys.platform,
    
        commitid='',
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
            A boolean that identifies if this is a version which was released to your users. Automated
            regression reports from SpeedTin may give warnings for slower measurements
            considering the run against the latest released version.
    
        :param branch:
            This is the branch of the code used to do the measurement.
            i.e.: master, development, ...
    
        :param str os:
            The os in which the benchmark was run (Windows, Linux, MacOs) 
    
        :param commitid:
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
        project_id = self.project_id
        authorization_key = self.authorization_key
        
        if not machine_name:
            import socket
            machine_name = socket.gethostname()
        
        if isinstance(commit_date, datetime.datetime):
            commit_date = self.date_to_str(commit_date)
        
        r = requests.post(
            '%s/api/projects/%s/benchmarks/%s/measurements' % (self.base_url, project_id, benchmark_id),
            json={
                'value': value,
                'version': version,
                'released': released,
                'branch': branch,
                'os': os,
                'commitid': commitid,
                'commit_date': commit_date,
                'machine_name': machine_name,
                'tag1': tag1,
                'tag2': tag2,
            },
            headers={'X-AuthToken': authorization_key}
        )
        if r.status_code != 201:
            raise AssertionError('It was not possible to create the measurement. Msg: %s' % (r.text,))
        return r.json()
    
    def run_and_get_output(self, *popenargs, **kwargs):
        '''
        Run command with arguments and return its output.
        '''
        timeout = None
        with subprocess.Popen(*popenargs, stdout=subprocess.PIPE, **kwargs) as process:
            try:
                output, unused_err = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                output, unused_err = process.communicate()
                raise subprocess.TimeoutExpired(process.args, timeout, output=output)
            except:
                process.kill()
                process.wait()
                raise
            retcode = process.poll()
            if retcode:
                raise subprocess.CalledProcessError(retcode, process.args, output=output)
        return output

    def git_commit_and_date_from_path(self, repo_path):
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
        commit_date = self.run_and_get_output(['git', 'show', '-s', '--format=%ct', commit_id]).strip().decode('utf-8')
        commit_date = datetime.datetime.utcfromtimestamp(int(commit_date))
        return commit_id, commit_date
            
            
        
        
if __name__ == '__main__':
    authorization_key = os.environ['SPEEDTIN_AUTHORIZATION_KEY']
    project_id = os.environ['SPEEDTIN_PROJECT_ID']
    api = PySpeedTinApi(authorization_key, project_id)
    api.create_benchmark('Test')
    commit_id, commit_date = api.git_commit_and_date_from_path(__file__)
    print(commit_id, commit_date)
#     api.create_measurement(benchmark_id='Test', value=2, version='2.2', released=True, branch='master', commitid, commit_date)
    
    