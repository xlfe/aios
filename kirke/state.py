import logging
logger = logging.getLogger('circe.state')

class State(object):
    """
    State is used for managing states and transitions.

    >>> from kirke.object import Object
    >>> class System(Object):
    ...     connectivity = State(['unknown', 'online', 'offline'])
    >>> system = System()
    >>> system.connectivity.__parent__ == system
    True
    >>> print(system.connectivity)
    connectivity=[UNKNOWN, online, offline]
    >>> system.connectivity.online = True
    >>> print(system)
    <System connectivity=[unknown, ONLINE, offline]>
    >>> system.connectivity == 'online'
    True
    >>> system.connectivity = 'offline'
    >>> print(system)
    <System connectivity=[unknown, online, OFFLINE]>
    >>> system.connectivity.__parent__ == system
    True
    """

    def __init__(self,  states=None, default=None):
        assert type(states) is list
        assert all(map(lambda _:_ == _.lower(), states)), 'states must be lower-case'
        self.states = states
        if default:
            assert default in self.states
        else:
            default = self.states[0]

        self.current_state = default

    def __set_name__(self, owner, name):
        self.__name__ = name

    @property
    def name(self):
        return getattr(self,'__name__', None)

    def __getattr__(self, item):
        if item not in self.__getattribute__('states'):
            raise AttributeError()

        if item == self.__getattribute__('current_state'):
            return True
        else:
            return False

    def change_state(self, new_state):
        assert new_state in getattr(self, 'states', [])
        cs = getattr(self, 'current_state', None)
        if new_state != cs:
            logger.debug('{}: {} -> {}'.format(self.name, cs, new_state))
            self.current_state = new_state
            return True
        return False

    def __set__(self, instance, value):
        if getattr(self,'__parent__',None) is None:
            self.__parent__ = instance
        self.change_state(value)

    def __setattr__(self, key, value):
        try:
            self.change_state(key)
        except AssertionError:
            super().__setattr__(key, value)

    def __repr__(self):
        states = map(lambda _:_.lower() if _ != self.current_state else _.upper(), self.states)
        return '{}=[{}]'.format(getattr(self,'__name__',''), ', '.join(states))

    def __eq__(self, other):
        if other in self.states:
            return other == self.current_state
        return super().__eq__(other)


