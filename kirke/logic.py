from kirke import state
from typing import Dict, Any, List, Callable, Tuple

class ConditionalInputOutput(object):
    """

    """

    def __init__(self,
                 condition: Callable,
                 inputs: List[Tuple['state.State', str]],
                 outputs: List[Tuple['state.State', str]]):

        self.condition = condition
        assert inputs and outputs
        assert all(map(state.State.check_state_tuple, inputs + outputs))

        async_required = any(_[0].check_for_async() for _ in outputs)

        idx = 0
        self.locks = dict()
        self.states = dict()
        self.conditions = dict()

        for source, source_state in inputs:

            source.output_callbacks.add(self.output_factory_async(idx) if async_required else self.output_factory(idx))
            self.conditions[idx] = source_state
            self.locks[idx] = None
            idx += 1


        self.inputs = inputs
        self.outputs = outputs
        self.idx = idx

    def notify_change(self):

        states = [self.conditions[idx] == self.states[idx] for idx in range(self.idx)]

        if self.condition(states) is not True:
            return

        #notify change to output objects

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
                self.parent.notify_change()

            async def release_lock(self):
                self.parent.locks[self.idx] = None

            def require_async(self):
                return True

        return AsyncOutput(self, idx)


    def output_factory(self):

        class Output(object):

            def acquire_lock(self, new_state):
                if self._lock is not None:
                    raise Exception('Change not allowed')
                self._lock = new_state
            def change(self):
                self.current_state = self._lock

            def release_lock(self):
                self._lock = None

            def require_async(self):
                return False

        return Output

