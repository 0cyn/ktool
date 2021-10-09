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
    <image src="https://pypip.in/v/k2l/badge.svg">
  </a>
    <br>
    <br>
</p>
    
Development is currently taking place on the [@python3.10 branch](https://github.com/KritantaDev/ktool/tree/python3.10). 

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


Run `ktool` after install for a list of commands and how to use them.

### Project purpose and goals

ktool is designed to be a powerful aid in reverse engineering/development for darwin systems.

It is written in python with *zero* compiled dependencies or platform stipulations (as a rule), meaning it can run anywhere python can run, with hopefully no BS/setup/compilation required.

The goal of this project is to provide an actively maintained, platform independent alternative to a ton of (*very useful, amazing*) tools available, and to package them as python libraries to be used in other projects.

### Documentation

https://ktool.rtfd.io

---

written in python for the sake of platform independence when operating on static binaries and libraries

#### Special thanks to

Blacktop for their amazing ipsw project: https://github.com/blacktop/ipsw  
if you haven't seen this yet, it's like my tool but stable and better and stuff. written in golang. it is a godsend.

JLevin and *OS Internals for extremely extensive documentation on previously undocumented APIs 

arandomdev for guidance + code
