try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

INSTALL_REQUIRES = ['distributed',
                    'dask-jobqueue',
                    ]
EXTRAS_REQUIRE = {}

setup(name='coffea_casa',
      version='0.0.1',
      packages=find_packages(),
      description='A Prototype U.S. CMS analysis facility',
      url='http://github.com/CoffeaTeam/coffea-casa.git',
      author='UNL',
      author_email='oksana.shadura@cern.ch',
      license='BSD-3-Clause License',
      install_requires=INSTALL_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      setup_requires=["pytest-runner", "flake8"],
      tests_require=["pytest"],
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
