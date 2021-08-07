# TODO
things to do before this is ready for a 1.0.0 release

### Fail gracefully

Currently this project's usual behaviour when encountering any kind of fault is to entirely exit and print a traceback

This is useful for debugging issues during development, and is a pain in the ass any other time than that.

Ideally hard-faulting could be re-enabled with some sort of argument or envar

### Things that need added

* DySymtab Parsing
* Lazy Binding Info Parsing

### Other things

* Proper (dont load entirety of objc metadata) .tbd dumping
* Lookup tables wherever possible
