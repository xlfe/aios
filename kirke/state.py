import logging
import inspect
import collections
from typing import Dict, Any, List, Callable

logger = logging.getLogger('circe.state')



class State(object):
    """
    State allows you to manage a state machine and state transitions and integrates with Circe Objects.

    >>> from kirke.object import Object
    >>> class System(Object):
    ...     def __init__(self, **kwargs):
    ...         self._circe_add_child('connectivity', State(['unknown', 'online', 'offline']))
    >>> system = System()
    >>> print(system)
    <System connectivity=[UNKNOWN, online, offline]>

    UPPERCASE states indicate that is the current state. You can assign
    truthy values to a state to enact a change

    >>> system.connectivity.ONLINE = True
    >>> print(system)
    <System connectivity=[unknown, ONLINE, offline]>

    You can also test equality against a state

    >>> system.connectivity == 'online'
    True

    Or apply a string to the object to change state
    >>> system.connectivity = 'offline'
    >>> print(system)
    <System connectivity=[unknown, online, OFFLINE]>
    """
    post_change_callback_maps: Dict['State', Dict]

    def __init__(self,  states: List =None, default: str=None, name=None):
        assert type(states) is list
        assert all(map(lambda _:_ == _.lower(), states)), 'states must be lower-case'
        self.states = states
        self.output_callbacks = set()
        self.post_change_callbacks = collections.defaultdict(list)
        if default:
            assert default in self.states
        else:
            default = self.states[0]

        self.current_state = default
        self.__name__ = name

    # def __hash__(self):
    #     return hash(self.__name__) + hash(self.__parent__)

    def __getattr__(self, item):
        """
        state object supports two access methods

        >>> s = State(name='test', states=['one', 'two'])
        >>> print(s)
        test=[ONE, two]

        The simple form is the uppercase state name, which returns True or False

        >>> print(s.TWO)
        False

        The lowercase form is used for linking states and returns a tuple of the class and the state

        >>> print(s.one)
        (test=[ONE, two], 'one')

        """
        if item.lower() not in self.__getattribute__('states'):
            raise AttributeError()

        if item.isupper():
            if item.lower() == self.__getattribute__('current_state'):
                return True
            else:
                return False
        elif item.islower():
            return (self, item)
        else:
            raise AttributeError()

    def change_state(self, new_state: str, source: 'State'=None):
        assert new_state in getattr(self, 'states', [])
        cs = getattr(self, 'current_state', None)
        if new_state != cs:
            if source is None:
                logger.debug('{}: {} -> {}'.format(self.__name__, cs, new_state))
            else:
                logger.debug('{}: {} -> {} (Source: {})'.format(self.__name__, cs, new_state, source))

            notified = []
            for obj in self.output_callbacks:
                try:
                    obj.will_change(new_state)
                    notified.append(obj)
                except:
                    for _ in notified:
                        _.wont_change()
                    raise

            for obj in self.output_callbacks:
                obj.has_changed(new_state)

            self.current_state = new_state

            for dest, dest_state in self.post_change_callbacks[new_state]:
                dest.change_state(dest_state, self)

    def __set__(self, instance, value):
        self.change_state(value, instance)

    def __setattr__(self, key, value):
        if key.lower() in getattr(self, 'states', []):

            if self.check_state_tuple(value):
                self.set_input({key: value})
            elif type(value) is list and all(self.check_state_tuple(_) for _ in value):
                map(lambda _:self.set_input({_[0]:_[1]}), value)
            else:
                self.change_state(key.lower())
                assert bool(value)
        else:
            super().__setattr__(key, value)

    def __repr__(self):
        states = map(lambda _:_.lower() if _ != self.current_state else _.upper(), self.states)
        return '{}=[{}]'.format(self.__name__, ', '.join(states))

    def __eq__(self, other):
        if other in self.states:
            return other == self.current_state
        return super().__eq__(other)

    @staticmethod
    def check_state_tuple(t):
        return type(t) is tuple and isinstance(t[0], State) and type(t[1]) is str

    def set_input(self, state_map: Dict):
        """
        You can also connect states together by setting one state object as the input for another

        >>> from kirke.object import Object
        >>> system = Object(name='system', children=dict(connectivity = State(['unknown', 'offline', 'online'])))
        >>> remote = Object(name='remote', children={'door':State(['closed', 'open'])})
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[UNKNOWN, offline, online]
        >>> remote.door.set_input(dict(
        ...     closed= [
        ...             system.connectivity.offline,
        ...             system.connectivity.unknown
        ...     ],
        ...     open= system.connectivity.online
        ... ))
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[UNKNOWN, offline, online]
        >>> system.connectivity.online = True
        >>> print(remote.door)
        door=[closed, OPEN]


        Or if you prefer, you can chain them like so

        >>> system = Object(name='system', children=dict(connectivity = State(['unknown', 'offline', 'online'])))
        >>> remote = Object(name='remote', children={'door':State(['closed', 'open'])})
        >>> very_remote = Object(name='very_remote', children={'alarm':State(['disarmed', 'armed'])})
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[UNKNOWN, offline, online]
        >>> print(very_remote.alarm)
        alarm=[DISARMED, armed]
        >>> remote.door.closed = [system.connectivity.offline, system.connectivity.unknown]
        >>> very_remote.alarm.armed = remote.door.open
        >>> remote.door.open = system.connectivity.online
        >>> system.connectivity.online = True
        >>> print(very_remote.alarm)
        alarm=[disarmed, ARMED]

        """

        for state, sources in state_map.items():

            if type(sources) is tuple:
                sources = [sources]
            all(self.check_state_tuple(_) for _ in sources)

            for dest, dest_state in sources:
                dest.post_change_callbacks[dest_state].append((self, state))




    def set_output(self, obj):
        """
        Changes to the State object output using a class that has the following methods:

        will_change(new_state)
        has_changed(new_state)
        wont_change()


        will_change is called first, to check whether the change will succeed. Raise an exception if the change
        will not succeed. Your implementation should guarantee that after not raising an exception during will_change
        the state change will succeed when has_changed is called. wont_change will be called if the change does
        not succeeed and will_change was called previously.

        The state will not change unless all outputs succeed

        >>> from kirke.object import Object
        >>> import logging
        >>> class GPIO(object):
        ...     def __init__(self):
        ...         self._can_change = True
        ...         self.current_state = None
        ...     def will_change(self, new_state):
        ...         if self._can_change is not True or self.current_state == new_state:
        ...             raise Exception('Change not allowed')
        ...     def has_changed(self, new_state):
        ...         self.current_state = new_state
        ...     def wont_change(self):
        ...         pass

        >>> system = Object(name='system', children={'connectivity': State(['offline', 'online'])})
        >>> gpio = GPIO()
        >>> system.connectivity.set_output(gpio)
        >>> print(system.connectivity)
        connectivity=[OFFLINE, online]
        >>> gpio.current_state == None
        True
        >>> system.connectivity = 'online'
        >>> print(gpio.current_state)
        online
        >>> gpio._can_change = False
        >>> system.connectivity = 'offline'
        Traceback (most recent call last):
        ...
        Exception: Change not allowed
        >>> system.connectivity == 'online'
        True



        """

        assert callable(obj.will_change) and callable(obj.has_changed) and callable(obj.wont_change)
        self.output_callbacks.add(obj)




