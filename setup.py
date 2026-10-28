from setuptools import setup

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='cbpi4-WhirlpoolStep',
      version='1.0.0',
      description='CraftBeerPi 4 Whirlpool Cooling Step Plugin',
      author='User',
      author_email='your.email@example.com',
      url='https://github.com/zzorrro/cbpi4-WhirlpoolStep',
      include_package_data=True,
      license='MIT',
      package_data={
        '': ['*.txt', '*.rst', '*.yaml'],
        'cbpi4-WhirlpoolStep': ['*','*.txt', '*.rst', '*.yaml']
      },
      packages=['cbpi4-WhirlpoolStep'],
      install_requires=['cbpi4'],
      long_description=long_description,
      long_description_content_type='text/markdown'
)