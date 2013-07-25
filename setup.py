"""
SQLAlchemy-Continuum
--------------------

Versioning and auditing extension for SQLAlchemy.
"""

from setuptools import setup, Command
import subprocess


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call(['py.test'])
        raise SystemExit(errno)

setup(
    name='SQLAlchemy-Continuum',
    version='0.8.0',
    url='https://github.com/kvesteri/sqlalchemy-continuum',
    license='BSD',
    author='Konsta Vesterinen',
    author_email='konsta@fastmonkeys.com',
    description='Versioning and auditing extension for SQLAlchemy.',
    long_description=__doc__,
    packages=[
        'sqlalchemy_continuum',
        'sqlalchemy_continuum.ext'
    ],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'SQLAlchemy>=0.8',
        'SQLAlchemy-Utils>=0.15.1',
        'inflection>=0.2.0'
    ],
    cmdclass={'test': PyTest},
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
