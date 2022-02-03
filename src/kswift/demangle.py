#
#  ktool | kswift
#  demangle.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2022.
#

def demangle(name):
    """
    Very basic, very sloppy bare minimum POC for swift classname demangling

    :param name:
    :return:
    """

    project = ""
    typename = ""
    stage = 0
    skip = False

    for c in name:
        if c.isdigit():
            if skip:
                continue
            else:
                stage += 1
                skip = True
                continue
        else:
            skip = False
            if stage == 0:
                continue
            elif stage == 1:
                project += c
            elif stage == 2:
                typename += c

    return project, typename
