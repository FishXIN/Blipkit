"""Latest-request-wins note rendering, without blocking the UI thread."""

import queue
import threading
from collections import OrderedDict

from .models import Note
from .sequencer import render_note
from .soundbank import get_preset


class NoteAuditioner:
    def __init__(self, renderer=render_note):
        self._render = renderer
        self._requests = queue.SimpleQueue()
        self._results = queue.SimpleQueue()
        self._generation = 0
        self._closed = False
        self._cache = OrderedDict()
        self._thread = threading.Thread(target=self._run, daemon=True, name="blipkit-audition")
        self._thread.start()

    def request(self, pitch, instrument, velocity, bpm, sample_rate):
        self._generation += 1
        self._requests.put((self._generation, (pitch, instrument, velocity, bpm, sample_rate)))

    def _run(self):
        while True:
            request = self._requests.get()
            if request is None:
                return
            while not self._requests.empty():
                request = self._requests.get()
                if request is None:
                    return
            generation, key = request
            try:
                samples = self._cache.get(key)
                if samples is None:
                    pitch, instrument, velocity, bpm, sample_rate = key
                    samples = self._render(
                        Note(pitch, 0, 0.45, velocity), bpm, get_preset(instrument), sample_rate
                    )
                    self._cache[key] = samples
                    if len(self._cache) > 64:
                        self._cache.popitem(last=False)
                self._cache.move_to_end(key)
                self._results.put((generation, samples, key[-1], None))
            except Exception as exc:
                self._results.put((generation, None, key[-1], str(exc)))

    def take_latest(self):
        result = None
        while not self._results.empty():
            candidate = self._results.get()
            if candidate[0] == self._generation and not self._closed:
                result = candidate[1:]
        return result

    def cancel(self):
        self._generation += 1

    def close(self):
        self._closed = True
        self.cancel()
        self._requests.put(None)
