"""Setup.py for coffea_casa
"""
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages
import io
import versioneer

# Add 'distributed' back when patches will be upstreamed
INSTALL_REQUIRES = ['dask-jobqueue']
TESTS_REQUIRE = ['pytest', 'pytest-cov'
                 'pytest-timeout', 'pytest-rerunfailures']
EXTRAS_REQUIRE = {
    'docs': ['ipython', 'sphinx', 'sphinx_rtd_theme',
             'sphinx-gallery', 'nbsphinx', 'nbstripout', 'docutils', 'sphinx_rtd_theme' , "mkdocs==1.2.4"],
    'test': ['pytest', 'pytest-cov', 'pytest-timeout', 'pytest-rerunfailures']
}

EXTRAS_REQUIRE['all'] = sorted(set(sum(EXTRAS_REQUIRE.values(), [])))

with io.open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

setup(name='coffea_casa',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      packages=find_packages(),
      description='A Prototype U.S. CMS analysis facility',
      long_description=readme,
      url='http://github.com/CoffeaTeam/coffea-casa.git',
      author='UNL',
      author_email='oksana.shadura@cern.ch',
      license='BSD-3-Clause License',
      install_requires=INSTALL_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      include_package_data=True,
      zip_safe=False,
      long_description_content_type = 'text/markdown',
      setup_requires=["pytest-runner", "flake8"],
      dependency_links=['git+git://github.com/oshadura/distributed.git@coffea-casa-facility#egg=distributed'],
      tests_require=TESTS_REQUIRE,
      classifiers=[
          "Development Status :: 4 - Beta",
          "Intended Audience :: Developers",
          "Intended Audience :: Information Technology",
          "Intended Audience :: Science/Research",
          "License :: OSI Approved :: BSD License",
          "Operating System :: POSIX",
          "Operating System :: Unix",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Topic :: Scientific/Engineering",
          "Topic :: Scientific/Engineering :: Information Analysis",
          "Topic :: Scientific/Engineering :: Mathematics",
          "Topic :: Scientific/Engineering :: Physics",
          "Topic :: Software Development",
          "Topic :: Utilities",
      ],
      platforms="Any",
      )
