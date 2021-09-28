from setuptools import setup

setup(name='ktool',
      version='0.9.0',
      description='Static mach-o/img4 analysis tool.',
      long_description='file: README.md',
      long_description_content_type='text/markdown',
      python_requires='>=3.10',
      author='kritanta',
      url='https://github.com/kritantadev/ktool',
      install_requires=['pyaes'],
      packages=['kimg4', 'kmacho', 'ktool'],
      package_dir={
            'kimg4': 'src/kimg4',
            'kmacho':'src/kmacho',
            'ktool': 'src/ktool'
      },
      classifiers=[
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent'
      ],
      scripts=['bin/ktool']
      )
