from setuptools import setup

setup(
    name='BotFather-CLI',
    version='0.1',
    py_modules=['botfather'],
    install_requires=[
        'Click',
    ],
    entry_points='''
        [console_scripts]
        botfather=botfather:cli
    ''',
)
