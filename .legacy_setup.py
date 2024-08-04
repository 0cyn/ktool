from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name = 'k2l',
    version = "2.1.1",
    description = 'Static MachO/ObjC Reverse Engineering Toolkit',
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
    packages = ['ktool_macho', 'ktool', 'ktool_swift'],
    package_dir = {
        'ktool_macho': 'src/ktool_macho',
        'lib0cyn': 'src/ktool_macho',
        'ktool': 'src/ktool',
        'ktool_swift': 'src/ktool_swift'
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
