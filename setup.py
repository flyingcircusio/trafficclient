from setuptools import setup, find_packages

setup(
    name='gocept.trafficclient',
    version='0.1',
    author='gocept',
    author_email='mail@gocept.com',
    url='https://svn.gocept.com/repos/gocept-int/',
    description="""\
    Measure traffic and report it to the traffic server.
    """,
    classifiers=[
        'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    license='gocept proprietary',
    install_requires=[
        'ZODB3',
        'fc.agent',
        'IPy',
        'mocker',
    ],
    entry_points={
        'console_scripts': [
            'trafficclient = gocept.trafficclient.client:main',
        ]
    },
)
