try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='pyspeedtin',
    version='0.1.0',
    description = 'Tool to upload performance data to SpeedTin',
    author='Fabio Zadrozny',
    url='https://www.speedtin.com',
    packages=['pyspeedtin'],
)

# Note: nice reference: https://jamie.curle.io/blog/my-first-experience-adding-package-pypi/
# New version: change version and then:
# python setup.py sdist
# python setup.py sdist register upload
