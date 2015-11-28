import datetime
import json
from os.path import os
import re

from pyspeedtin.system_mutex import timed_acquire_mutex

def date_to_str(date):
    return date.strftime('%Y-%m-%d %H:%M:%S.%f')

def json_dumps(obj):
    return json.dumps(obj, default=default_convert)

def default_convert(obj):
    if obj.__class__ == datetime.datetime:
        return date_to_str(obj)
    raise TypeError("Type not serializable: %s" % (obj,))

class _HandleData(object):

    def __init__(self, handle_data):
        self._handle_data = handle_data
        self._changed = False
        self._remove = False

    def has_rest_data(self):
        return bool(self._handle_data.get('rest_data'))

    def set_rest_data(self, rest_data):
        self._handle_data['rest_data'] = rest_data
        self._changed = True

    def remove(self):
        self._changed = True
        self._remove = True

    data = property(lambda self: self._handle_data['data'])
    rest_data = property(lambda self: self._handle_data['rest_data'])

try:
    xrange  # @UndefinedVariable
except:
    xrange = range


class _IteratorWithRemove(object):

    def __init__(self, lst):
        self.lst = lst
        self.i = 0

    def remove(self):
        del self.lst[self.i]
        self.i -= 1

    def __iter__(self):
        while True:
            if self.i >= len(self.lst):
                break
            yield self.lst[self.i]
            self.i += 1


class _Bucket(object):

    def __init__(self, local_cache, bucket_name):
        self._local_cache = local_cache
        self._bucket_name = bucket_name
        self._mutex_handle = None

    def __enter__(self, *args, **kwargs):
        self._mutex_handle = mutex_handle = timed_acquire_mutex(_get_mutex_name(self._bucket_name))
        mutex_handle.__enter__()
        return self

    def __exit__(self, *args, **kwargs):
        self._mutex_handle.__exit__()
        self._mutex_handle = None

    def __iter__(self):
        assert self._mutex_handle is not None
        contents_file = self._local_cache._get_contents_file(self._bucket_name)
        data = self._local_cache._get_current_data(contents_file)
        it = _IteratorWithRemove(data)
        for handle_data in it:
            h = _HandleData(handle_data)
            yield h
            if h._changed:
                if h._remove:
                    it.remove()
                with open(contents_file, 'w') as stream:
                    stream.write(json_dumps((data)))


def check_valid_bucket_name(bucket_name):
    # To be windows/linux compatible we can't use non-valid filesystem names
    regexp = re.compile(r'[\*\?"<>|/\\:]')
    result = regexp.findall(bucket_name)
    if result is not None and len(result) > 0:
        raise AssertionError('Bucket name is invalid: %s' % (bucket_name,))


def _get_mutex_name(bucket):
    return 'pyspeedtin_%s' % (bucket,)


class LocalCache(object):

    def __init__(self, data_dir):
        self._data_dir = data_dir
        try:
            os.makedirs(data_dir)
        except:
            pass

    def add(self, bucket_name, data, rest_data=''):
        check_valid_bucket_name(bucket_name)
        with timed_acquire_mutex(_get_mutex_name(bucket_name)):
            contents_file = self._get_contents_file(bucket_name)
            initial_data = self._get_current_data(contents_file)

            for handle_data in initial_data:
                # Don't add duplicate data
                if handle_data['data'] == data:
                    return

            handle_data = {
                'rest_data': rest_data,
                'data': data,
            }

            initial_data.append(handle_data)
            with open(contents_file, 'w') as stream:
                stream.write(json_dumps(initial_data))

    def clear(self, bucket_name):
        check_valid_bucket_name(bucket_name)
        with timed_acquire_mutex(_get_mutex_name(bucket_name)):
            contents_file = self._get_contents_file(bucket_name)
            if os.path.exists(contents_file):
                os.remove(contents_file)
        
    def load(self, bucket_name):
        check_valid_bucket_name(bucket_name)
        return _Bucket(self, bucket_name)

    # Private API (system mutex must be held already).
    def _get_current_data(self, contents_file):
        initial_data = []
        if os.path.exists(contents_file):
            with open(contents_file, 'r') as stream:
                current_contents = stream.read()
                if current_contents:
                    initial_data = json.loads(current_contents)
        return initial_data

    def _get_contents_file(self, bucket_name):
        contents_file = os.path.join(self._data_dir, bucket_name)
        return contents_file
