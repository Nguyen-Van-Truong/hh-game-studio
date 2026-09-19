import copy
import unittest
from clock_join import join_interval, offset_interval, JoinError


def fixture():
    anchors=[{'kind':'ACK','batch':4,'host_before_publish_us':1099,
              'host_after_receipt_us':1101,'native_observed_us':100}]
    samples=[{'host_before_ns':t*1000,'host_after_ns':(t+1)*1000,
              'kernel_100ns':i*100,'user_100ns':i*200,'tid':20,'thread_created_100ns':12345}
             for i,t in enumerate((1090,1110,1140,1170,1210,1230))]
    return anchors,samples


class JoinTests(unittest.TestCase):
    def test_conservative_envelope_keeps_uncertainty(self):
        result=join_interval(120,200,*fixture())
        self.assertEqual(result['status'],'OBSERVED_ENVELOPE')
        self.assertEqual((result['offset_low_us'],result['offset_high_us']),(997,1003))
        self.assertEqual((result['first_sample'],result['last_sample']),(1,4))
        self.assertEqual(result['cpu_delta_100ns'],900)
        self.assertFalse(result['exact_call_cpu_available'])
        self.assertEqual(result['wait_cause'],'UNKNOWN')
        self.assertFalse(result['overhead_subtracted'])

    def test_no_anchor_or_no_enclosing_sample_is_unknown(self):
        anchors,samples=fixture()
        for a,s in (([],samples),(anchors,[]),(anchors,samples[2:]),(anchors,samples[:4])):
            with self.subTest(a=a,s=len(s)):
                self.assertEqual(join_interval(120,200,a,s)['status'],'UNKNOWN')

    def test_disjoint_offsets_never_average(self):
        anchors,samples=fixture()
        anchors.append({'kind':'ACK','host_before_publish_us':2200,
                        'host_after_receipt_us':2201,'native_observed_us':100})
        self.assertEqual(join_interval(120,200,anchors,samples)['status'],'UNKNOWN')

    def test_identity_time_and_cpu_regressions_are_unknown(self):
        for key,value in (('tid',21),('thread_created_100ns',12346),('kernel_100ns',0),
                          ('user_100ns',0),('host_before_ns',1),('host_after_ns',1),
                          ('host_after_ns',None)):
            with self.subTest(key=key):
                anchors,samples=fixture(); samples[2][key]=value
                self.assertEqual(join_interval(120,200,anchors,samples)['status'],'UNKNOWN')

    def test_no_native_host_direct_subtraction_or_interpolation(self):
        a,s=fixture()
        shifted=copy.deepcopy(s)
        for row in shifted:
            row['host_before_ns']+=10**15; row['host_after_ns']+=10**15
        anchor=copy.deepcopy(a)
        anchor[0]['host_before_publish_us']+=10**12
        anchor[0]['host_after_receipt_us']+=10**12
        original=join_interval(120,200,a,s)
        result=join_interval(120,200,anchor,shifted)
        self.assertEqual(result['cpu_delta_100ns'],original['cpu_delta_100ns'])
        self.assertEqual(result['native_wall_us'],80)

    def test_returned_publish_time_cannot_replace_before_stamp(self):
        a,s=fixture(); del a[0]['host_before_publish_us']; a[0]['ack_written_mono_us']=1101
        self.assertEqual(join_interval(120,200,a,s)['status'],'UNKNOWN')

    def test_bad_or_reversed_anchor_rejected(self):
        for row in ({'kind':'START'}, {'kind':'ACK','host_before_publish_us':2,
                                     'host_after_receipt_us':1,'native_observed_us':0}):
            with self.assertRaises(JoinError):offset_interval([row])


if __name__=='__main__':unittest.main(verbosity=2)
