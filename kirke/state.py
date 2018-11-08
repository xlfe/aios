import logging
import asyncio
import time
import inspect
import collections
from typing import Dict, Any, List, Callable

logger = logging.getLogger('circe.state')

# notify
# cancel
# begin
# completed

# acquire lock
# change state
# release lock



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

    def check_change_state(self, new_state: str, source: 'State'=None):
        assert new_state in getattr(self, 'states', [])
        cs = getattr(self, 'current_state', None)
        if new_state == cs:
            return False

        if source is None:
            logger.debug('{}: {} -> {}'.format(self.__name__, cs, new_state))
        else:
            logger.debug('{}: {} -> {} (Source: {})'.format(self.__name__, cs, new_state, source))

        return True

    async def change_state_async(self, new_state: str, source: 'State'=None):
        """

        >>> from kirke.object import Object
        >>> import asyncio
        >>> class GPIO_Async(object):
        ...     def __init__(self):
        ...         self._lock = None
        ...         self.current_state = None
        ...     async def acquire_lock(self, new_state):
        ...         if self._lock is not None:
        ...             raise Exception('Change not allowed')
        ...         self._lock = new_state
        ...     async def change(self):
        ...         await asyncio.sleep(1)
        ...         self.current_state = self._lock
        ...     async def release_lock(self):
        ...         self._lock = None
        ...     def require_async(self):
        ...         return True
        >>> system = Object(name='system', children={'connectivity': State(['offline', 'online'])})
        >>> gpio = GPIO_Async()
        >>> system.connectivity.set_output(gpio)
        >>> loop = asyncio.get_event_loop()
        >>> loop.run_until_complete(system.connectivity.change_state_async('offline'))
        >>> print(system.connectivity)
        connectivity=[OFFLINE, online]
        >>> loop.run_until_complete(system.connectivity.change_state_async('online'))
        >>> print(system.connectivity)
        connectivity=[offline, ONLINE]
        """
        if not self.check_change_state(new_state, source):
            return

        locked = []
        locked_async = []
        for obj in self.output_callbacks:

            try:
                if obj.require_async():
                    await obj.acquire_lock(new_state)
                    locked_async.append(obj)
                else:
                    obj.acquire_lock(new_state)
                    locked.append(obj)
            except:
                for _ in locked:
                    _.release_lock()
                for _ in locked_async:
                    await _.release_lock()
                raise

        for _ in locked:
            _.change()

        for _ in locked_async:
            await _.change()

        for dest, dest_state in self.post_change_callbacks[new_state]:
            await dest.change_state_async(dest_state, self)

        self.current_state = new_state

        for _ in locked:
            _.release_lock()
        for _ in locked_async:
            await _.release_lock()


    def check_for_async(self):

        assert all(_.require_async() is False for _ in self.output_callbacks), \
            "At least one of the output callbacks requires awaiting - use change_state_async instead."

        checked = list()
        for new_state in self.post_change_callbacks:
            for dest, dest_state in self.post_change_callbacks[new_state]:
                if dest in checked:
                    continue
                dest.check_for_async()
                checked.append(dest)

    def change_state(self, new_state: str, source: 'State'=None):
        if not self.check_change_state(new_state, source):
            return

        self.check_for_async()

        locked = []
        for obj in self.output_callbacks:
            try:
                obj.acquire_lock(new_state)
                locked.append(obj)
            except:
                for _ in locked:
                    _.release_lock()
                raise

        for _ in self.output_callbacks:
             _.change()

        for dest, dest_state in self.post_change_callbacks[new_state]:
            dest.change_state(dest_state, self)

        self.current_state = new_state

        for _ in self.output_callbacks:
            _.release_lock()

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

        - acquire_lock(new_state)

        Notify the desire to change state - called first.

        Raise an exception to block the change from proceeding (eg if another state object already has a lock).

        Your implementation should guarantee that after not raising
        an exception during acquire_lock, a call to change() will succeed.

        - change_state()
        Notify that a change is proceeding - (the change can be made now).

        - release_lock()

        Release the lock. If change() was called, only release the lock once the change
        has been enacted. If change() was not called, release_lock immediately.

        - require_async()

        Indicate if the calls are async or not. See change_state_async()

        >>> from kirke.object import Object
        >>> class GPIO(object):
        ...     def __init__(self):
        ...         self._lock = None
        ...         self.current_state = None
        ...     def acquire_lock(self, new_state):
        ...         if self._lock is not None:
        ...             raise Exception('Change not allowed')
        ...         self._lock = new_state
        ...     def change(self):
        ...         self.current_state = self._lock
        ...     def release_lock(self):
        ...         self._lock = None
        ...     def require_async(self):
        ...         return False
        >>> system = Object(name='system', children={'connectivity': State(['offline', 'online'])})
        >>> gpio = GPIO()
        >>> system.connectivity.set_output(gpio)

        Note, that if you haven't defined a default for your State object, it starts in an
        "undefined" state (where no state is considered active) :-

        >>> print(system.connectivity)
        connectivity=[offline, online]

        Note that changes from undefined states will also propagate...

        >>> system.connectivity = 'offline'
        >>> gpio.current_state == 'offline'
        True

        >>> gpio._lock = True
        >>> system.connectivity = 'online'
        Traceback (most recent call last):
        ...
        Exception: Change not allowed
        >>> system.connectivity == 'offline'
        True
        """

        assert callable(obj.acquire_lock) and \
               callable(obj.change) and \
               callable(obj.release_lock) and \
               callable(obj.require_async)
        self.output_callbacks.add(obj)




