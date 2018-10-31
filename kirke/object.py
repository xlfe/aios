import logging, inspect
logger = logging.getLogger('circe.object')

from .state import State

class Object(object):
    """
    The Object class forms the basis of the Circe system.

    It does a number of things

    To use Circe, the first thing to do is create a class that inherits
    from Object for each type of object in your overall system.

    When instantiating your class, the following (optional) Circe keywords can be specified:-

    * name
    * children

    >>> class System(Object):
    ...     pass
    >>> class Node(Object):
    ...     pass
    >>> system = System(name='iot', children={'endpoint': Node()})
    >>> print(system.endpoint)
    <iot.endpoint>

    Child objects access the parent class using the __parent__ attribute, set during __init__

    >>> assert system.endpoint.__parent__ is system

    Your Object derived classes can have their own __init__, but you must
    include **kwargs to capture arbitrary arguments which are used by Circe

    >>> class System(Object):
    ...     def __init__(self, device_mac, **kwargs):
    ...         self.device_mac = device_mac
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    >>> assert system.device_mac == 'ab:cd:ef:gh:12' and system.__name__ == 'iot'

    The Circe hierarchy is setup after the child classes are created, so things will
    break if you try to use a Circe construct during your classes __init__

    >>> class Node(Object):
    ...     def __init__(self, **kwargs):
    ...         assert self.__parent__
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    Traceback (most recent call last):
    ...
    AttributeError: 'Node' object has no attribute '__parent__'

    If you need to perform setup or initialisation tasks on any Circe Children objects
    using Circe constructs, define a __circe__child__init__ function (which has no arguments)


    >>> class Node(Object):
    ...     def __circe__child__init__(self):
    ...         self.__parent__.__name__ = 'node-123'
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    >>> print(system.endpoint)
    <node-123.endpoint>

    You don't need to do this on the top Class of your Circe hierarchy though

    >>> class System(Object):
    ...     def __init__(self, device_mac, **kwargs):
    ...         self.device_mac = device_mac
    ...         for name, obj in self._circe_children.items():
    ...             obj.__name__ = 'MAC:{}-{}'.format(device_mac, name)
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    >>> print(system.endpoint)
    <node-123.MAC:ab:cd:ef:gh:12-endpoint>


    """

    def __new__(cls, *args, **kwargs):
        o = super().__new__(cls)

        name = kwargs.pop('name', None)
        if name:
            setattr(o, '__name__', name)
        setattr(o, '_circe_children', kwargs.pop('children', {}))
        for name, obj in  o._circe_children.items():
            #all children are already instances
            obj.__parent__ = o
            obj.__name__ = name
            setattr(o, name, obj)
            try:
                obj.__circe__child__init__()
            except AttributeError:
                pass

        return o

    def __branch__(self):
        _=[]
        parent = self
        while True:
            try:
                _.append(parent)
                parent = getattr(parent, '__parent__')
            except (AttributeError):
                _.reverse()
                return _

    def __repr__(self):
        names = map(lambda _:getattr(_, '__name__', _.__class__.__name__), self.__branch__())
        states = ' '.join(map(lambda _:_[1].__repr__(), inspect.getmembers(self, lambda _:isinstance(_, State))))
        return '<{}{}>'.format('.'.join(names), (' ' if states else '') + states)











