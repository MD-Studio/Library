# coding=utf-8
import mock
from twisted.internet.defer import Deferred
from twisted.trial.unittest import TestCase

from mdstudio.db.cursor import Cursor, CursorRefreshingError
from mdstudio.deferred.chainable import chainable


# noinspection PyPep8
class CursorTests(TestCase):
    def setUp(self):
        self.wrapper = mock.Mock()

        self.wrapper.more = mock.MagicMock(return_value={'alive': False, 'results': []})

        self.values = [
            {'test': 5},
            {'test2': 2}
        ]
        self.result = {
            'cursorId': 1234,
            'alive': True,
            'results': self.values
        }
        self.cursor = Cursor(self.wrapper, self.result)

    def test_construction(self):

        self.assertEqual(self.cursor._id, 1234)
        self.assertEqual(self.cursor._alive, True)
        self.assertEqual(len(self.cursor._data), 2)

    @chainable
    def test_next(self):

        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})

    @chainable
    def test_next2(self):

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': True, 'results': []})
        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})
        self.assertRaises(StopIteration, lambda: next(self.cursor))

    @chainable
    def test_next3(self):

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': True, 'results': [{'test3': 6}]})
        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})
        self.assertEqual((yield next(self.cursor)), {'test3': 6})

    @chainable
    def test_next4(self):

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': [{'test3': 6}]})
        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})
        self.assertEqual((yield next(self.cursor)), {'test3': 6})

    @chainable
    def test_list(self):
        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': [{'test6': 2}]})

        self.assertEqual((yield self.cursor.to_list()), self.values + [{'test6': 2}])

    def test_list_raise(self):
        self.wrapper.more = mock.MagicMock(return_value=Deferred())

        self.assertRaises(CursorRefreshingError, lambda: list(self.cursor))

    @chainable
    def test_iter_stop(self):

        for i, v in enumerate(self.cursor):
            self.assertEqual((yield v), self.values[i])

        self.wrapper.more.assert_called_with(**{'cursor_id': 1234})

    @chainable
    def test_more(self):
        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': True, 'results': [{'test3': 8}]})

        nxt = lambda: next(self.cursor)
        self.assertEqual((yield nxt()), {'test': 5})
        self.assertEqual((yield nxt()), {'test2': 2})

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': [{'test6': 2}]})
        self.assertEqual((yield nxt()), {'test3': 8})

        self.assertEqual((yield nxt()), {'test6': 2})

        self.assertRaises(StopIteration, nxt)

    @chainable
    def test_id(self):
        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1244, 'alive': True, 'results': [{'test3': 8}]})

        nxt = lambda: next(self.cursor)
        self.assertEqual((yield nxt()), {'test': 5})
        self.assertEqual((yield nxt()), {'test2': 2})

        self.wrapper.more.assert_called_with(**{'cursor_id': 1234})
        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': [{'test6': 2}]})

        self.assertEqual((yield nxt()), {'test3': 8})

        self.wrapper.more.assert_called_with(**{'cursor_id': 1244})

        self.assertEqual((yield nxt()), {'test6': 2})

        self.assertRaises(StopIteration, nxt)

    @chainable
    def test_foreach(self):

        hist = {'test': 0, 'test2': 0}

        def test(o):
            for k, v in o.items():
                hist[k] += v

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': []})
        yield self.cursor.for_each(test)

        self.assertEqual(hist['test'], 5)
        self.assertEqual(hist['test2'], 2)

    @chainable
    def test_query(self):

        self.wrapper.more = mock.MagicMock(return_value={'cursorId': 1234, 'alive': False, 'results': []})
        results = yield self.cursor.query().select(lambda x: True if 'test' in x else False).to_list()

        self.assertEqual(len(results), 2)
        self.assertEqual(results, [True, False])

    def test_count(self):

        self.wrapper.count = mock.MagicMock(return_value={'total': 2})
        self.assertEqual(self.cursor.count(), 2)
        self.wrapper.count.assert_called_with(**{'cursor_id': 1234, 'with_limit_and_skip': False})

    def test_count2(self):

        self.wrapper.count = mock.MagicMock(return_value={'total': 2})
        self.assertEqual(self.cursor.count(True), 2)
        self.wrapper.count.assert_called_with(**{'cursor_id': 1234, 'with_limit_and_skip': True})

    @chainable
    def test_len(self):

        self.wrapper.count = mock.MagicMock(return_value={'total': 2})
        self.assertEqual((yield len(self.cursor)), 2)
        self.wrapper.count.assert_called_with(**{'cursor_id': 1234, 'with_limit_and_skip': True})

    @chainable
    def test_rewind(self):

        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})

        self.wrapper.rewind = mock.MagicMock(return_value=self.result)
        self.assertEqual((yield self.cursor.rewind()), self.cursor)

        self.assertEqual((yield next(self.cursor)), {'test': 5})
        self.assertEqual((yield next(self.cursor)), {'test2': 2})

    @chainable
    def test_rewind2(self):

        self.wrapper.rewind = mock.MagicMock(return_value=self.result)

        nxt = lambda: next(self.cursor)
        self.assertEqual((yield nxt()), {'test': 5})
        self.assertEqual((yield nxt()), {'test2': 2})

        self.cursor = yield self.cursor.rewind()

        nxt = lambda: next(self.cursor)
        self.assertEqual((yield nxt()), {'test': 5})
        self.assertEqual((yield nxt()), {'test2': 2})
