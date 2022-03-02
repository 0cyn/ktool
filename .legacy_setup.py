from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name = 'k2l',
    version = "1.0.0",
    description = 'Static MacO/ObjC Reverse Engineering Toolkit',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    python_requires = '>=3.6',
    author = 'cynder',
    license = 'MIT',
    url = 'https://github.com/cxnder/ktool',
    install_requires = [
        'pyaes',
        'kimg4',
        'Pygments'
    ],
    packages = ['kmacho', 'ktool', 'kswift'],
    package_dir = {
        'kmacho': 'src/kmacho',
        'ktool': 'src/ktool',
        'kswift': 'src/kswift'
    },
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent'
    ],
    entry_points = {'console_scripts': [
        'ktool=ktool.ktool_script:main'
    ]},
    project_urls = {
        'Documentation': 'https://ktool.cynder.me/en/latest/ktool.html',
        'Issue Tracker': 'https://github.com/cxnder/ktool/issues'
    }
)
