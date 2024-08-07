"""
SQLAlchemy-Continuum
--------------------

Versioning and auditing extension for SQLAlchemy.
"""

import os
import sys
import re
from setuptools import setup


HERE = os.path.dirname(os.path.abspath(__file__))
PY3 = sys.version_info[0] == 3


def get_version():
    filename = os.path.join(HERE, 'sqlalchemy_continuum', '__init__.py')
    with open(filename) as f:
        contents = f.read()
    pattern = r"^__version__ = '(.*?)'$"
    return re.search(pattern, contents, re.MULTILINE).group(1)


extras_require = {
    'test': [
        'pytest>=2.3.5',
        'psycopg2>=2.4.6',
        'PyMySQL>=0.8.0',
    ],
    'flask': ['Flask>=0.9'],
    'flask-login': ['Flask-Login>=0.2.9'],
    'flask-sqlalchemy': ['Flask-SQLAlchemy>=1.0'],
    'i18n': ['SQLAlchemy-i18n>=0.8.4,!=1.1.0'],
}


# Add all optional dependencies to testing requirements.
for name, requirements in extras_require.items():
    if name != 'test':
        extras_require['test'] += requirements


setup(
    name='SQLAlchemy-Continuum',
    version=get_version(),
    url='https://github.com/kvesteri/sqlalchemy-continuum',
    license='BSD',
    author='Konsta Vesterinen',
    author_email='konsta@fastmonkeys.com',
    description='Versioning and auditing extension for SQLAlchemy.',
    long_description=__doc__,
    packages=[
        'sqlalchemy_continuum',
        'sqlalchemy_continuum.plugins',
        'sqlalchemy_continuum.dialects'
    ],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'SQLAlchemy>=1.4.0',
    ],
    extras_require=extras_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
