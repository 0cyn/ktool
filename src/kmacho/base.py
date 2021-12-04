#
#  ktool | kmacho
#  base.py
#
#
#
#  This file is part of ktool. ktool is free software that
#  is made available under the MIT license. Consult the
#  file "LICENSE" that is distributed together with this file
#  for the exact licensing terms.
#
#  Copyright (c) kat 2021.
#

from abc import ABC, abstractmethod


class Constructable(ABC):
    """
    This is an attempt to define a standardized API for objects we load and may want to create.

    The idea is that all objects should be loadable and serializable in both directions, to allow patching, creation,
        and standard loading, with hopefully not too much overhead being shared between the three.

    """

    @staticmethod
    @abstractmethod
    def from_bytes(*args, **kwargs):
        """
        Base method for serializing an instance of the subclass based on raw bytes

        Implementation/Args left up to implementations, but should usually follow `from_bytes(raw: bytes)`

        :return:
        """

    @staticmethod
    @abstractmethod
    def from_values(*args, **kwargs):
        """
        Base method for serializing an instance of the subclass based on the required set of values to create it.

        Implementation and argument structure of this is definitely left up to subclasses.

        :return:
        """

    @abstractmethod
    def raw_bytes(self):
        """
        Built or stored raw byte representation of this item

        :return:
        """
