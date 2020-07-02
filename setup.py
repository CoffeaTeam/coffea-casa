try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

setup(name='coffea_casa',
      version='0.0.1',
      packages=find_packages(),
      description='A Prototype U.S. CMS analysis facility',
      url='http://github.com/CoffeaTeam/coffea-casa.git',
      author='UNL',
      author_email='oksana.shadura@cern.ch',
      license='BSD-3-Clause License',
      install_requires=['distributed','dask-jobqueue'],
      zip_safe=False
      )
