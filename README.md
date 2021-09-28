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
    <code>pip3 install k2l</code>
</p>

### Installation

```shell
# Installtion
pip3 install k2l

# Updating
pip3 install --upgrade k2l
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
