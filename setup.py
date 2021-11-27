from setuptools import setup

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(name='k2l',
      version='0.15.6',
      description='Static mach-o/img4 analysis tool.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      python_requires='>=3.6',
      author='kritanta',
      url='https://github.com/kritantadev/ktool',
      install_requires=['pyaes', 'kimg4', 'Pygments', 'packaging'],
      packages=['kmacho', 'ktool'],
      package_dir={
            'kmacho': 'src/kmacho',
            'ktool': 'src/ktool'
      },
      classifiers=[
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent'
      ],
      scripts=['bin/ktool']
      )
