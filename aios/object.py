import logging, inspect
logger = logging.getLogger('aios.object')

from .state import State

class Object(object):
    """Object forms the basis of the aios system.

    To use aios, the first thing to do is create a class that inherits
    from Object for each type of object in your overall system.

    When instantiating your class, the following (optional) aios keywords can be specified:-

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
    include **kwargs to capture arbitrary arguments which are used by aios

    >>> class System(Object):
    ...     def __init__(self, device_mac, **kwargs):
    ...         self.device_mac = device_mac
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    >>> assert system.device_mac == 'ab:cd:ef:gh:12' and system.__name__ == 'iot'

    The aios hierarchy is setup after the child classes are created, so things will
    break if you try to use a aios construct during your classes __init__

    >>> class Node(Object):
    ...     def __init__(self, **kwargs):
    ...         assert self.__parent__
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    Traceback (most recent call last):
    ...
    AttributeError: 'Node' object has no attribute '__parent__'

    If you need to perform setup or initialisation tasks on any aios Children objects
    using aios constructs, define a _aios_child_init function (which has no arguments)
    and when you're aios system has been instantiated, call _aios_state_init() on the top
    level object :-


    >>> class Node(Object):
    ...     def _aios_child_init(self):
    ...         self.__parent__.__name__ = 'node-123'
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})
    >>> print(system)
    <iot <iot.endpoint>>
    >>> system._aios_state_init()
    <node-123 <node-123.endpoint>>

    Note - you don't need to use the _aios_child_init on the top Class of your
    aios hierarchy though, because all of the child objects have been instantiated by the time
    __init__ is run on that top object.

    >>> class System(Object):
    ...     def __init__(self, device_mac, **kwargs):
    ...         self.device_mac = device_mac
    ...         for name, obj in self._aios_children.items():
    ...             obj.__name__ = 'MAC:{}-{}'.format(device_mac, name)
    >>> system = System(name='iot', device_mac='ab:cd:ef:gh:12', children={'endpoint': Node()})._aios_state_init()
    >>> print(system.endpoint)
    <node-123.MAC:ab:cd:ef:gh:12-endpoint>

    You can add children to an object at any time, but names must be unique for each parent

    >>> system._aios_add_child('endpoint', Node())
    Traceback (most recent call last):
    ...
    Exception: An object named "endpoint" was already defined on "node-123"
    """

    def __new__(cls, *args, **kwargs):
        o = super().__new__(cls)

        setattr(o, '__name__', kwargs.pop('name', cls.__name__))
        setattr(o, '_aios_children', {})
        for name, obj in  kwargs.pop('children', {}).items():
            #all children are already instances
            o._aios_add_child(name, obj)

        return o

    def _aios_add_child(self, name, obj):
        try:
            getattr(self, name)
            raise Exception('An object named "{}" was already defined on "{}"'.format(name, self.__name__))
        except (AttributeError):
            pass
        obj.__parent__ = self
        obj.__name__ = name
        setattr(self, name, obj)
        self._aios_children[name] = obj

    def _aios_state_init(self):
        for name, obj in getattr(self, '_aios_children', {}).items():
            if hasattr(obj, '_aios_child_init') and callable(obj._aios_child_init):
                obj._aios_child_init()
                obj._aios_state_init()
        return self

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
        names = map(lambda _:_.__name__, self.__branch__())
        states = ' '.join(map(lambda _:_.__repr__(), self._aios_children.values()))
        return '<{}{}>'.format('.'.join(names), (' ' if states else '') + states)

    def __setattr__(self, attr, val):
        """capture attribute assignment of instance variables"""
        try:
            obj = object.__getattribute__(self, attr)
        except AttributeError:
            # This will be raised if we are setting the attribute for the first time
            # i.e inside `__init__` in your case.
            object.__setattr__(self, attr, val)
        else:
            if hasattr(obj, '__set__'):
                obj.__set__(self, val)
            else:
                object.__setattr__(self, attr, val)










