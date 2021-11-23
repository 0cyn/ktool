from setuptools import setup

setup(name='k2l',
      version='0.14.10',
      description='Static mach-o/img4 analysis tool.',
      long_description='file: README.md',
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
