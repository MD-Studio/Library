import json
import time
from datetime import timedelta

import os
from autobahn.wamp import ApplicationError, TransportLost
from mock import mock, call
from pyfakefs.fake_filesystem_unittest import Patcher

from mdstudio.api.exception import CallException
from mdstudio.deferred.chainable import test_chainable
from mdstudio.logging.impl.session_observer import SessionLogObserver
from mdstudio.logging.log_type import LogType
from mdstudio.unittest.db import DBTestCase
from mdstudio.utc import from_utc_string, now, to_utc_string, timestamp

# Python 2 compatibility.
try:
    TimeoutError
except NameError:
    import socket
    TimeoutError = socket.timeout

class SessionObserverTests(DBTestCase):

    def setUp(self):
        SessionLogObserver._instance = None
        self.session = mock.MagicMock()
        self.session.__str__ = mock.MagicMock(return_value='"MagicMock"')
        self.session.component_root_path = mock.MagicMock(return_value='/')

        self.observer = SessionLogObserver(self.session)
        self.observer.flusher = mock.MagicMock()

    def tearDown(self):
        SessionLogObserver._instance = None

    def test_construction(self):
        self.assertEqual(self.observer.session, None)
        self.assertEqual(self.observer.sessions, [])
        self.assertEqual(self.observer.log_type, LogType.User)

        self.assertLessEqual(now() - from_utc_string(self.observer.logs[0]['time']), timedelta(seconds=1))
        del self.observer.logs[0]['time']
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver',
            'message': 'Collecting logs on session "MagicMock"'
        }])
        self.assertEqual(self.observer.flushing, False)
        self.assertEqual(os.path.abspath(self.observer.recovery_file(self.session)), os.path.abspath('/logs/recovery.json'))

    def test_call(self):
        t = now()
        self.observer({
            'log_format': 'hello {str}',
            'log_namespace': 'test namespace',
            'log_level': LogType.Group,
            'log_time': timestamp(t),
            'str': 'test'
        })

        self.assertLessEqual(t - from_utc_string(self.observer.logs[1]['time']), timedelta(seconds=1))
        del self.observer.logs[1]['time']
        self.assertEqual(self.observer.logs[1], {
            'level': 'Group',
            'source': 'test namespace',
            'message': 'hello test'
        })

    def test_call2(self):
        t = now()
        self.observer({
            'message': 'hello test',
            'log_namespace': 'test namespace',
            'log_level': LogType.Group,
            'log_time': timestamp(t),
        })

        self.assertLessEqual(t - from_utc_string(self.observer.logs[1]['time']), timedelta(seconds=1))
        del self.observer.logs[1]['time']
        self.assertEqual(self.observer.logs[1], {
            'level': 'Group',
            'source': 'test namespace',
            'message': 'hello test'
        })

    def test_call3(self):
        self.observer({
            'message': '',
            'log_namespace': 'test namespace',
            'log_level': LogType.Group,
            'log_time': time.mktime(now().timetuple()),
        })

        self.assertEqual(len(self.observer.logs), 1)

    @test_chainable
    def test_store_recovery(self):
        with Patcher() as patcher:
            self.observer.session = self.session
            patcher.fs.MakeDirectory('/logs')

            self.assertLessEqual(now() - from_utc_string(self.observer.logs[0]['time']), timedelta(seconds=1))
            del self.observer.logs[0]['time']
            self.assertEqual(self.observer.logs, [{
                'level': 'info',
                'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver',
                'message': 'Collecting logs on session "MagicMock"'
            }])

            yield self.observer.store_recovery()
            self.assertEqual(self.observer.logs, [])
            with open(self.observer.recovery_file(self.session)) as f:
                self.assertEqual(json.load(f), [{
                    'level': 'info',
                    'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver',
                    'message': 'Collecting logs on session "MagicMock"'
                }])

    @test_chainable
    def test_store_recovery2(self):
        with Patcher() as patcher:
            self.observer.session = self.session
            patcher.fs.MakeDirectory('/logs')

            self.observer.logs = []

            yield self.observer.store_recovery()
            self.assertEqual(self.observer.logs, [])
            self.assertFalse(os.path.isfile(self.observer.recovery_file(self.session)))

    @test_chainable
    def test_flush_logs(self):
        self.observer.session = self.session
        self.session.flush_logs = mock.MagicMock()
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [])
        self.session.flush_logs.assert_called_once_with([{
            'level': 'info',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver',
            'message': 'Collecting logs on session "MagicMock"'
        }])

    @test_chainable
    def test_flush_logs2(self):
        def raise_(ex):
            raise ex

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(TimeoutError))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'message': 'Collecting logs on session "MagicMock"',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver'
        }])
        self.observer.sleep.assert_has_calls([
            call(3),
            call(1)
        ])

    @test_chainable
    def test_flush_logs3(self):
        def raise_(ex):
            raise ex

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(ApplicationError))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'message': 'Collecting logs on session "MagicMock"',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver'
        }])
        self.observer.sleep.assert_has_calls([
            call(1)
        ])

    @test_chainable
    def test_flush_logs4(self):
        def raise_(ex):
            raise ex

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(TransportLost))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'message': 'Collecting logs on session "MagicMock"',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver'
        }])
        self.observer.sleep.assert_has_calls([
            call(1),
            call(1)
        ])

    @test_chainable
    def test_flush_logs5(self):
        def raise_(ex):
            raise ex

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(CallException))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'message': 'Collecting logs on session "MagicMock"',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver'
        }])
        self.observer.sleep.assert_has_calls([
            call(1),
            call(1)
        ])

    @test_chainable
    def test_flush_logs6(self):
        def raise_(ex):
            raise ex()

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.observer.log.error = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(Exception))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [{
            'level': 'info',
            'message': 'Collecting logs on session "MagicMock"',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver'
        }])
        self.observer.log.error.assert_called_once()

    @test_chainable
    def test_flush_logs7(self):
        def raise_(ex):
            raise ex()

        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.observer.log.error = mock.MagicMock()
        self.session.flush_logs = mock.MagicMock(wraps=lambda ex: raise_(Exception))
        self.observer.logs = []
        yield self.observer.flush_logs()
        self.assertEqual(self.observer.logs, [])

    @test_chainable
    def test_flush_logs8(self):
        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.observer.log.error = mock.MagicMock()
        self.observer.logs = [0] * 9
        yield self.observer.flush_logs()
        self.observer.sleep.assert_has_calls([
            call(1)
        ])

    @test_chainable
    def test_flush_logs9(self):
        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        self.observer.log = mock.MagicMock()
        self.observer.log.error = mock.MagicMock()
        self.observer.logs = [0] * 10
        yield self.observer.flush_logs()
        self.observer.sleep.assert_not_called()

    @test_chainable
    def test_start_flushing(self):
        self.observer.session = self.session
        self.observer.sleep = mock.MagicMock()
        yield self.observer.start_flushing(self.session)

        self.assertLessEqual(now() - from_utc_string(self.observer.logs[0]['time']), timedelta(seconds=1))
        del self.observer.logs[0]['time']
        yield self.observer.flush_logs()

        self.assertFalse(os.path.isfile(self.observer.recovery_file(self.session)))

        self.assertEqual(self.observer.logs, [])
        self.session.flush_logs.assert_called_once_with([{
            'level': 'info',
            'source': 'mdstudio.logging.impl.session_observer.SessionLogObserver',
            'message': 'Collecting logs on session "MagicMock"'
        }])

        self.assertEqual(self.observer.session, self.session)

    @test_chainable
    def test_start_flushing2(self):
        with Patcher() as patcher:
            patcher.fs.CreateFile(self.observer.recovery_file(self.session), contents=json.dumps([{'est': 'error'}]))

            self.observer.session = self.session
            self.observer.sleep = mock.MagicMock()
            yield self.observer.start_flushing(self.session)
            self.assertEqual(self.observer.logs, [{'est': 'error'}])

            yield self.observer.flush_logs()

            self.assertFalse(os.path.isfile(self.observer.recovery_file(self.session)))

            self.session.flush_logs.assert_called_once_with([{'est': 'error'}])
            self.assertEqual(self.observer.session, self.session)

    @test_chainable
    def test_start_flushing3(self):
        with Patcher() as patcher:
            patcher.fs.CreateFile(self.observer.recovery_file(self.session), contents='sdfwef')

            self.observer.session = self.session
            self.observer.sleep = mock.MagicMock()
            yield self.observer.start_flushing(self.session)
            self.assertNotEqual(self.observer.logs, 'sdfwef')

    @test_chainable
    def test_start_flushing4(self):
        with Patcher() as _:
            self.observer.session = self.session
            self.observer.sleep = mock.MagicMock()
            self.observer.flushing = True
            yield self.observer.start_flushing(self.session)
            self.assertNotEqual(self.observer.logs, 'sdfwef')
            self.assertEqual(self.observer.sessions, [self.session])

    def test_pause_flushing(self):
        self.observer.pause_flushing(self.session)

    def test_pause_flushing2(self):
        self.observer.flushing = True
        self.observer.sessions = [self.session]
        self.observer.pause_flushing(self.session)
        self.assertEqual(self.observer.sessions, [])

    def test_pause_flushing3(self):
        self.observer.flushing = True
        self.observer.session = self.session
        self.observer.sessions = [self.session]
        self.observer.pause_flushing(self.session)
        self.assertEqual(self.observer.sessions, [])
