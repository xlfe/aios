import asyncio
from kirke import state
from typing import Dict, Any, List, Callable, Tuple
import logging
logger = logging.getLogger('circe.logic')

class ConditionalInputOutput(object):
    """

    >>> from kirke import State
    >>> A = State(['enabled', 'disabled'], name='A', default='disabled')
    >>> B = State(['enabled', 'disabled'], name='B', default='disabled')
    >>> O = State(['enabled', 'disabled'], name='O')
    >>> ConditionalInputOutput(all, [A.enabled, B.enabled], [O.enabled])
    <kirke.logic.ConditionalInputOutput object at 0x...>
    >>> ConditionalInputOutput(any, [A.disabled, B.disabled], [O.disabled])
    <kirke.logic.ConditionalInputOutput object at 0x...>
    >>> print(O)
    O=[enabled, DISABLED]
    >>> A.enabled = True
    >>> print(O)
    O=[enabled, DISABLED]
    >>> B.enabled = True
    >>> print(O)
    O=[ENABLED, disabled]
    >>> A.disabled = True
    >>> print(O)
    O=[enabled, DISABLED]
    """

    def __init__(self,
                 condition: Callable,
                 inputs: List[Tuple['state.State', str]],
                 outputs: List[Tuple['state.State', str]]):

        self.condition = condition
        assert inputs and outputs
        assert all(map(state.State.check_state_tuple, inputs + outputs))

        self.async_required = async_required = any(_[0].check_for_async() for _ in outputs)

        logger.debug('{} has Async Required: {}'.format(condition.__name__, async_required))

        idx = 0
        self.locks = dict()
        self.states = dict()
        self.conditions = dict()
        factory = self.output_factory_async if async_required else self.output_factory

        for source, source_state in inputs:

            source.output_callbacks.add(factory(idx))
            self.conditions[idx] = source_state
            self.states[idx] = source.current_state
            self.locks[idx] = None
            idx += 1

        self.inputs = inputs
        self.outputs = outputs
        self.idx = idx

        if async_required:
            asyncio.ensure_future(self.notify_change_async())
        else:
            self.notify_change()

    def notify_change(self):

        states = [self.conditions[idx] == self.states[idx] for idx in range(self.idx)]

        logger.debug('{} notify_change with states {}'.format(self, states))

        if self.condition(states) is not True:
            return

        #notify change to output objects
        for dest, dest_state in self.outputs:
            dest.change_state(dest_state, self)

    async def notify_change_async(self):

        states = [self.conditions[idx] == self.states[idx] for idx in range(self.idx)]

        if self.condition(states) is not True:
            return

        #notify change to output objects
        for dest, dest_state in self.outputs:
            await dest.change_state_async(dest_state, self)


    def output_factory_async(self, idx):

        class AsyncOutput(object):

            def __init__(self, parent, idx):
                self.parent = parent
                self.idx = idx

            async def acquire_lock(self, new_state):
                if self.parent.locks[self.idx] is not None:
                    raise Exception('Change not allowed')
                self.parent.locks[self.idx] = new_state

            async def change(self):
                self.parent.states[self.idx] = self.parent.locks[self.idx]
                self.parent.notify_change_async()

            async def release_lock(self):
                self.parent.locks[self.idx] = None

            def require_async(self):
                return True

        return AsyncOutput(self, idx)


    def output_factory(self, idx):

        class Output(object):

            def __init__(self, parent, idx):
                self.parent = parent
                self.idx = idx

            def acquire_lock(self, new_state):
                if self.parent.locks[self.idx] is not None:
                    raise Exception('Change not allowed')
                self.parent.locks[self.idx] = new_state

            def change(self):
                self.parent.states[self.idx] = self.parent.locks[self.idx]
                self.parent.notify_change()

            def release_lock(self):
                self.parent.locks[self.idx] = None

            def require_async(self):
                return False

        return Output(self, idx)

