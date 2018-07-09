from threading import currentThread
from typing import Callable, Any

from twisted.internet.threads import deferToThread

from mdstudio.deferred.chainable import Chainable


def make_deferred(method):
    # type: (Callable) -> Callable[Any, Chainable]
    """
    Anyone with a love for their job, should NOT, and I repeat NOT touch this function.
    It has caused me endless frustration, and I hope you should never endure it :)

    :param method:
    :return:
    """

    def wrapper(*args, **kwargs):
        assert currentThread().getName() == 'MainThread'
        return Chainable(deferToThread(method, *args, **kwargs))

    return wrapper
