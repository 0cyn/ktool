<p align="center">
<img src=".github/svg/logo.png" alt="Logo" width=450px> 
</p>
<h4 align="center">
MachO/ObjC Analysis + Editing toolkit.
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

Commands:

GUI (Still in active development) ---
    ktool open [filename] - Open the ktool command line GUI and browse a file

MachO Editing ---
    insert - Utils for inserting load commands into MachO Binaries
    edit - Utils for editing MachO Binaries
    lipo - Utilities for combining/separating slices in fat MachO files.

MachO Analysis ---
    dump - Tools to reconstruct certain files (headers, .tbds) from compiled MachOs
    list - Print various lists (Classlist, etc.)
    symbols - Print various tables (Symbols, imports, exports)
    info - Print misc info about the target mach-o

Misc Utilities ---
    file - Print very basic info about the MachO
    img4 - IMG4 Utilities
    

Run `ktool [command]` for info/examples on using that command
```

### Documentation

https://ktool.rtfd.io

---

written in pure, 100% python for the sake of platform independence when operating on static binaries and libraries. 
this should run on any and all implementations of python3.

#### Special thanks to

JLevin and *OS Internals for existing

arandomdev for guidance + code

Blacktop for their amazing ipsw project: https://github.com/blacktop/ipsw  
