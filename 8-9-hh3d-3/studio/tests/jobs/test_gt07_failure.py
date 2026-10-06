import unittest

from studio.tests.jobs.gt07_failure import failure_boundary


class FailureBoundaryTests(unittest.TestCase):
    def test_wrapper_preserves_typed_cause_without_message_or_locals(self):
        class TypedError(RuntimeError):
            code = 'NATIVE_CAUSE'
        secret = 'Bearer-do-not-record'
        try:
            try:
                raise TypedError(secret)
            except TypedError as cause:
                raise RuntimeError(secret) from cause
        except RuntimeError as error:
            receipt = failure_boundary(error)
        self.assertNotIn(secret, repr(receipt))
        self.assertEqual(receipt['causes'][0]['code'], 'NATIVE_CAUSE')
        self.assertEqual(receipt['causes'][0]['frames'][-1]['file'],
                         'test_gt07_failure.py')

    def test_cyclic_or_long_causes_are_bounded_and_invalid_code_is_omitted(self):
        first = ValueError('secret')
        first.code = 'secret with spaces'
        previous = first
        for _ in range(20):
            following = RuntimeError('secret')
            previous.__cause__ = following
            previous = following
        previous.__cause__ = first
        receipt = failure_boundary(first)
        self.assertEqual(receipt['code'], 'ValueError')
        self.assertEqual(len(receipt['causes']), 7)
        self.assertNotIn('secret', repr(receipt))


if __name__ == '__main__':
    unittest.main()
