import logging, inspect
logger = logging.getLogger('circe.object')

from .state import State

OTHER_CIRCE_TYPES = [State]

class Object(object):
    """
    The Circe Object is the root of the Circe state system

    >>> class Node(Object):
    ...     pass
    >>> class System(Object):
    ...     CIRCE_SUB_OBJECTS = {'Node':Node}
    ...     def __init__(self, system_ident):
    ...         self.__name__ = system_ident

    >>> system = System('system-123')
    >>> system.endpoint = system.Node()
    >>> print(system)
    <system-123>
    >>> print(system.endpoint)
    <system-123.endpoint>
    >>> system.endpoint.__parent__ == system
    True
    """

    CIRCE_SUB_OBJECTS = {}

    def __getattr__(self, item):

        obj = self.CIRCE_SUB_OBJECTS.get(item)

        if obj is None:
            raise AttributeError()

        def wrapper(*args, **kwargs):
            _ = obj.__new__(obj)
            setattr(_, '__parent__', self)
            _.__init__(*args, **kwargs)
            return _

        return wrapper

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

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if isinstance(value, tuple([Object] + OTHER_CIRCE_TYPES)):
            if getattr(value, '__name__', None) is None:
                value.__name__ = name
            # if getattr(value, '__parent__', None) is None:
            #     raise Exception(name)
            #     value.__parent__ = self

    def __new__(cls, *args, **kwargs):
        o = super().__new__(cls)
        for name, state in inspect.getmembers(o, lambda _:isinstance(_, State)):
            state.__parent__ = o
        return o










