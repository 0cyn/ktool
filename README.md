# ktool
Static Mach-O binary metadata analysis tool / information dumper

[![tests](https://github.com/kritantadev/ktool/actions/workflows/tests.yml/badge.svg)](https://github.com/kritantadev/ktool/actions/workflows/tests.yml)
[![docs](https://readthedocs.org/projects/ktool/badge/?version=latest)](https://ktool.rtfd.io)
[![version](https://pypip.in/v/k2l/badge.svg)](https://pypi.org/project/k2l/)

### Installation

```shell
# Installtion
pip3 install k2l

# Updating
pip3 install --upgrade k2l
```

### Documentation

https://ktool.rtfd.io

### ktool commands


ktool includes both a library, and a script which uses that library to perform various tasks. 

It'll add the command `ktool` to the python scripts directory (`pyenv exec ktool` if using pyenv)

```shell
usage: ktool [command] <flags> [filename]

ktool dump:
ktool dump --headers --out <directory> [filename] - Dump set of headers for a bin/framework
ktool dump --tbd [filename] - Dump .tbd for a framework

ktool file:
ktool file [filename] - Prints (very) basic info about a file (e.g. "Thin MachO Binary")

ktool lipo:
ktool lipo --extract [slicename] [filename] - Extract a slice from a fat binary
ktool lipo --create [--out filename] [filenames] - Create a fat MachO Binary from multiple thin binaries

ktool list:
ktool list --symbols [filename] - Print the symbol table for the file
ktool list --classes [filename] - Print the list of classes
ktool list --protocols [filename] - Print the list of protocols
ktool list --linked [filename] - Print a list of linked libraries

ktool info:
usage: ktool info [-h] [--slice SLICE_INDEX] [--vm] [--cmds] [--binding] filename
ktool info [--slice n] [filename] - Print generic info about a MachO File
ktool info [--slice n] --vm [filename] - Print VM -> Slice -> File address mapping for a slice of a MachO File
ktool info [--slice n] --cmds [filename] - Print list of load commands for a file 
ktool info [--slice n] --binding [filename] - Print binding actions for a file

```

---

written in python for the sake of platform independence when operating on static binaries and libraries

#### Special thanks to

IDA for making it possible to write the code without actually understanding full internals  
JLevin and *OS Internals Vol 1 for actually understanding the internals and specifics + writing documentation  
arandomdev for guidance + code
