import logging
import asyncio
import time
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
    ...         self._circe_add_child('connectivity', State(['online', 'offline']))
    >>> system = System()

    If you don't specify a default state, the state is undefined to begin with :-

    >>> print(system)
    <System connectivity=[online, offline]>

    UPPERCASE states indicate that is the current state. You can assign
    truthy values to a state to enact a change

    >>> system.connectivity.ONLINE = True
    >>> print(system)
    <System connectivity=[ONLINE, offline]>

    You can also test equality against a state

    >>> system.connectivity == 'online'
    True

    Or apply a string to the object to change state
    >>> system.connectivity = 'offline'
    >>> print(system)
    <System connectivity=[online, OFFLINE]>
    """
    post_change_callback_maps: Dict['State', Dict]

    def __init__(self,  states: List =None, default: str=None, name=None):
        assert type(states) is list
        assert all(map(lambda _:_ == _.lower(), states)), 'states must be lower-case'
        self.states = states
        self.output_callbacks = set()
        self.post_change_callbacks = collections.defaultdict(list)
        self.__name__ = name
        if default is not None:
            assert default in self.states
            self.current_state = default
        else:
            self.current_state = None


    # def __hash__(self):
    #     return hash(self.__name__) + hash(self.__parent__)

    def __getattr__(self, item):
        """
        state object supports two access methods

        >>> s = State(name='test', states=['one', 'two'], default='one')
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
                    obj.notify(new_state)
                    notified.append(obj)
                except:
                    for _ in notified:
                        _.cancel()
                    raise

            for obj in self.output_callbacks:
                obj.begin(new_state)

            while not all(_.completed(new_state) for _ in self.output_callbacks):
                time.sleep(0.01)

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
        >>> system = Object(name='system', children=dict(connectivity = State(['slow', 'offline', 'online'], default='offline')))
        >>> remote = Object(name='remote', children={'door':State(['closed', 'open'], default='closed')})
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[slow, OFFLINE, online]
        >>> remote.door.set_input(dict(
        ...     closed= [
        ...             system.connectivity.offline,
        ...             system.connectivity.slow
        ...     ],
        ...     open= system.connectivity.online
        ... ))
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[slow, OFFLINE, online]
        >>> system.connectivity.online = True
        >>> print(remote.door)
        door=[closed, OPEN]


        Or if you prefer, you can chain them like so

        >>> system = Object(name='system', children=dict(connectivity = State(['slow', 'offline', 'online'], default='offline')))
        >>> remote = Object(name='remote', children={'door':State(['closed', 'open'], default='closed')})
        >>> very_remote = Object(name='very_remote', children={'alarm':State(['disarmed', 'armed'])})
        >>> print(remote.door)
        door=[CLOSED, open]
        >>> print(system.connectivity)
        connectivity=[slow, OFFLINE, online]
        >>> print(very_remote.alarm)
        alarm=[disarmed, armed]
        >>> remote.door.closed = [system.connectivity.offline, system.connectivity.slow]
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
        """Changes to the State object output using a class that has the following methods:

        All of these functions should be non-blocking.

        - notify(new_state)
        Notify the desire to change state - called first.
        Raise an exception to block the change from proceeding.
        Your implementation should guarantee that after not raising
        an exception during notify it will change state after begin is called.

        - cancel()
        Called to cancel the notified change (eg one of the other outputs raised an Exception)

        - begin(new_state)
        Notify that a change is proceeding - (the change can be made now).

        - completed(new_state)
        Check whether a change has completed - return True to signify the change was
        successful or False to signify the change is still in progress.

        >>> from kirke.object import Object
        >>> import logging
        >>> class GPIO(object):
        ...     def __init__(self):
        ...         self._can_change = True
        ...         self.current_state = None
        ...     def notify(self, new_state):
        ...         if self._can_change is not True or self.current_state == new_state:
        ...             raise Exception('Change not allowed')
        ...     def begin(self, new_state):
        ...         self.current_state = new_state
        ...     def completed(self, new_state):
        ...         return True
        ...     def cancel(self):
        ...         pass
        >>> system = Object(name='system', children={'connectivity': State(['offline', 'online'])})
        >>> gpio = GPIO()
        >>> system.connectivity.set_output(gpio)
        >>> print(system.connectivity)
        connectivity=[offline, online]
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

        assert callable(obj.notify) and \
               callable(obj.cancel) and \
               callable(obj.begin) and \
               callable(obj.completed)
        self.output_callbacks.add(obj)




