<h2 align="center">
  ktool
</h2>
<h4 align="center">
Static Mach-O binary metadata analysis tool / information dumper
</h4>
<p align="center">
  <a href="https://github.com/kritantadev/ktool/actions/workflows/tests.yml">
    <image src="https://github.com/kritantadev/ktool/actions/workflows/tests.yml/badge.svg">
  </a>
  <a href="https://ktool.rtfd.io">
    <image src="https://readthedocs.org/projects/ktool/badge/?version=latest">
  </a>
  <a href="https://pypi.org/project/k2l/">
    <image src="https://badge.fury.io/py/k2l.svg">
  </a>
    <br>
    <br>
</p>
    
### Installation

```shell
# Installing
pip3 install k2l

# Updating
pip3 install --upgrade k2l
```

### Usage 

```
> $ ktool
Usage: ktool [command] <flags> [filename]
    
    Commands for ktool:

    MachO ---
        dump - Tools to reconstruct certain files (headers, .tbds) from compiled MachOs
        file - Print very basic info about the MachO
        lipo - Utilities for combining/separating slices in fat MachO files.
        list - Dumps certain tables from MachOs
        info - Dump misc info about the target mach-o

    IMG4  ---
        img4 - IMG4 Utilities
    
    Run `ktool [command]`  for info/examples on using that command
```

### Documentation

https://ktool.rtfd.io

---

written in pure, 100% python for the sake of platform independence when operating on static binaries and libraries. 
this should run on any and all implementations of python3.

#### Special thanks to

JLevin and *OS Internals for extremely extensive documentation on previously undocumented APIs 

arandomdev for guidance + code

Blacktop for their amazing ipsw project: https://github.com/blacktop/ipsw  
