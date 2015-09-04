from setuptools import setup, find_packages

setup(
    name='fc.trafficclient',
    version='0.2',
    author='Christian Theune',
    author_email='ct@flyingcircus.io',
    url='https://bitbucket.org/flyingcircus/trafficclient',
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
    license='BSD 2-clause',
    install_requires=[
        'ZODB3',
        'fc.agent',
        'IPy',
        'mock',
    ],
    entry_points={
        'console_scripts': [
            'trafficclient = fc.trafficclient.client:main',
        ]
    },
)
