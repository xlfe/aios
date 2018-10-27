import logging
import inspect
from typing import Dict, Any, List

logger = logging.getLogger('circe.state')


check_signature = lambda _:list(inspect.signature(_[0]).parameters.keys()) == _[1]

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
    post_change_callback_maps: Dict['State', Dict]

    def __init__(self,  states: List =None, default: str=None):
        assert type(states) is list
        assert all(map(lambda _:_ == _.lower(), states)), 'states must be lower-case'
        self.states = states
        self.post_change_callback_maps = dict()
        if default:
            assert default in self.states
        else:
            default = self.states[0]

        self.current_state = default

    def __hash__(self):
        return hash(self.__name__) + hash(self.__parent__)

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

    def change_state(self, new_state: str, source: 'State'=None):
        assert new_state in getattr(self, 'states', [])
        cs = getattr(self, 'current_state', None)
        if new_state != cs:
            if source is None:
                logger.debug('{}: {} -> {}'.format(self.name, cs, new_state))
            else:
                logger.debug('{}: {} -> {} (Source: {})'.format(self.name, cs, new_state, source))

            self.current_state = new_state
            for dest, incoming_state_map in self.post_change_callback_maps.items():
                self.map_change_callback(dest, incoming_state_map, new_state, source)
        return False

    def __set__(self, instance, value):
        if getattr(self,'__parent__',None) is None:
            self.__parent__ = instance
        self.change_state(value, instance)

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

    def set_input(self, input: 'State', incoming_state_map: Dict, allow_incomplete_map: bool=False, replace_existing: bool=False):
        """
        You can also connect states together by setting one state object as the input for another

        >>> from kirke.object import Object
        >>> class System(Object):
        ...     connectivity = State(['unknown', 'offline', 'online'])
        >>> system = System()
        >>> class Remote(Object):
        ...     door = State(['closed', 'open'])
        >>> remote = Remote()
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[UNKNOWN, offline, online]
        >>> state_mapping = {
        ...     'online':'open',
        ...     'offline':'closed'
        ... }
        >>> remote.door.set_input(input=system.connectivity, incoming_state_map=state_mapping)
        Traceback (most recent call last):
        ...
        ValueError: Either define a default state using None as a key or map all incoming states

        You must map all states, or set a default
        >>> remote.door.set_input(input=system.connectivity, incoming_state_map=state_mapping, allow_incomplete_map=True)

        But only one input map per state object
        >>> remote.door.set_input(input=system.connectivity, incoming_state_map=state_mapping, allow_incomplete_map=True)
        Traceback (most recent call last):
        ...
        ValueError: Duplicate input objects not allowed
        >>> remote.door.set_input(input=system.connectivity, incoming_state_map=state_mapping, allow_incomplete_map=True, replace_existing=True)
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[UNKNOWN, offline, online]
        >>> system.connectivity.online = True
        >>> print(remote.door)
        door=[closed, OPEN]
        """
        if allow_incomplete_map is False:
            if None not in incoming_state_map and len(input.states) != len(incoming_state_map):
                raise ValueError('Either define a default state using None as a key or map all incoming states')

        input.add_post_change_callback_map(self, incoming_state_map, replace_existing)

    def map_change_callback(self, dest, incoming_state_map, new_state, source=None):

        dest_state = incoming_state_map.get(new_state, None)

        if dest_state is None:
            dest_state = incoming_state_map.get(None)

        dest.change_state(dest_state, source)

    def add_post_change_callback_map(self, dest, incoming_state_map, replace_existing):
        """
        add a callback on state change that will be called with two arguments :-
            self, new_state

        """
        if dest in self.post_change_callback_maps and not replace_existing:
            raise ValueError('Duplicate input objects not allowed')
        self.post_change_callback_maps[dest] = incoming_state_map




