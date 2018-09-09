from setuptools import setup

setup(
    name='codegrade',
    version='1.0.0',
    description='a simple autograder',
    author='Adrian Sampson',
    author_email='asampson@cs.cornell.edu',
    url='https://github.com/sampsyo/codegrade',
    license='MIT',
    platforms='ALL',

    install_requires=['click'],

    py_modules=['codegrade'],

    entry_points={
        'console_scripts': [
            'codegrade = codegrade:codegrade',
        ],
    },

    classifiers=[
        'Environment :: Console',
        'Programming Language :: Python :: 3',
    ],
)
