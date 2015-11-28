# License: LGPL
#
# Copyright: Brainwy Software
'''
To use, create a SystemMutex, check if it was acquired (get_mutex_aquired()) and if acquired the
mutex is kept until the instance is collected or release_mutex is called.

I.e.:

    mutex = SystemMutex('my_unique_name')
    if mutex.get_mutex_aquired():
        print('acquired')
    else:
        print('not acquired')
    
    
Or to keep trying to get the mutex until a given timeout elapses:

    with timed_acquire_mutex('mutex_name'):
        # Do something without any racing condition with other processes
        ...

'''

import re
import sys
import tempfile
import time
import traceback
import weakref

from pyspeedtin.null import NULL


def check_valid_mutex_name(mutex_name):
    # To be windows/linux compatible we can't use non-valid filesystem names
    # (as on linux it's a file-based lock).

    regexp = re.compile(r'[\*\?"<>|/\\:]')
    result = regexp.findall(mutex_name)
    if result is not None and len(result) > 0:
        raise AssertionError('Mutex name is invalid: %s' % (mutex_name,))

if sys.platform == 'win32':

    import os

    class SystemMutex(object):

        def __init__(self, mutex_name):
            check_valid_mutex_name(mutex_name)
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                os.unlink(filename)
            except:
                pass
            try:
                handle = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                try:
                    try:
                        pid = str(os.getpid())
                    except:
                        pid = 'unable to get pid'
                    os.write(handle, pid)
                except:
                    pass  # Ignore this as it's pretty much optional
            except:
                self._release_mutex = NULL
                self._acquired = False
            else:
                def release_mutex(*args, **kwargs):
                    # Note: can't use self here!
                    if not getattr(release_mutex, 'called', False):
                        release_mutex.called = True
                        try:
                            os.close(handle)
                        except:
                            traceback.print_exc()
                        try:
                            # Removing is optional as we'll try to remove on startup anyways (but
                            # let's do it to keep the filesystem cleaner).
                            os.unlink(filename)
                        except:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()

else:  # Linux
    import os
    import fcntl  # @UnresolvedImport

    class SystemMutex(object):

        def __init__(self, mutex_name):
            check_valid_mutex_name(mutex_name)
            filename = os.path.join(tempfile.gettempdir(), mutex_name)
            try:
                handle = open(filename, 'w')
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except:
                self._release_mutex = NULL
                self._acquired = False
                try:
                    handle.close()
                except:
                    pass
            else:
                def release_mutex(*args, **kwargs):
                    # Note: can't use self here!
                    if not getattr(release_mutex, 'called', False):
                        release_mutex.called = True
                        try:
                            fcntl.flock(handle, fcntl.LOCK_UN)
                        except:
                            traceback.print_exc()
                        try:
                            handle.close()
                        except:
                            traceback.print_exc()
                        try:
                            # Removing is pretty much optional (but let's do it to keep the
                            # filesystem cleaner).
                            os.unlink(filename)
                        except:
                            pass

                # Don't use __del__: this approach doesn't have as many pitfalls.
                self._ref = weakref.ref(self, release_mutex)

                self._release_mutex = release_mutex
                self._acquired = True

        def get_mutex_aquired(self):
            return self._acquired

        def release_mutex(self):
            self._release_mutex()


class _MutexHandle(object):

    def __init__(self, system_mutex):
        self._system_mutex = system_mutex

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        self._system_mutex.release_mutex()


try:
    xrange  # @UndefinedVariable
except:
    xrange = range


def timed_acquire_mutex(mutex_name, attempts=20, sleep_time=.5):
    '''
    Acquires the mutex given its name, a number of attempts and a time to sleep between each attempt.

    :throws RuntimeError if it was not possible to get the mutex in the given time.

    To be used as:

    with timed_acquire_mutex('mutex_name'):
        # Do something without any racing condition with other processes
        ...
    '''
    for _i in xrange(attempts):
        mutex = SystemMutex(mutex_name)
        if not mutex.get_mutex_aquired():
            time.sleep(sleep_time)
            mutex = None
        else:
            return _MutexHandle(mutex)
    else:
        raise RuntimeError(
            'Could not get mutex: %s after: %s secs.' %
            (mutex_name, attempts * sleep_time))
