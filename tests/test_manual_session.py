import sys,unittest,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
from manual_session import ManualSession

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.a=self.root/'a.jpg';self.b=self.root/'b.jpg';self.a.write_bytes(b'top fixture');self.b.write_bytes(b'side fixture')
        self.log=self.root/'audit.jsonl';self.s=ManualSession(self.log)
        self.s.select('top',self.a);self.s.select('side',self.b)
        self.result=dict(status='candidate',class_name='red_cube')
    def complete(self):
        job,_=self.s.start();self.s.finish(job,self.result)
    def test_rerun_same_pair_not_new_sample(self):
        self.complete();self.s.record('red_cube');self.complete()
        with self.assertRaisesRegex(ValueError,'已记录'):self.s.record('red_cube')
        self.assertEqual(self.s.statistics()['total'],1)
    def test_renamed_copies_and_swapped_order_still_deduplicated(self):
        self.complete();self.s.record('red_cube');c=self.root/'renamed.jpg';shutil.copy2(self.a,c)
        self.s.select('top',self.b);self.s.select('side',c);self.complete()
        with self.assertRaises(ValueError):self.s.record('red_cube')
    def test_pending_job_cannot_record_previous_result_or_change_selection(self):
        self.complete();self.s.start()
        with self.assertRaises(ValueError):self.s.record('red_cube')
        with self.assertRaises(ValueError):self.s.select('top',self.a)
    def test_stale_callback_ignored(self):
        job,_=self.s.start();self.assertFalse(self.s.finish(job-1,self.result));self.assertTrue(self.s.busy)
        self.assertTrue(self.s.finish(job,self.result))
    def test_changed_file_during_prediction_counts_failure(self):
        job,_=self.s.start();self.a.write_bytes(b'changed fixture');self.s.finish(job,self.result);self.s.record('red_cube')
        self.assertEqual(self.s.statistics(),dict(total=1,correct=0,success_rate=0))
    def test_explicit_truth_correction_keeps_denominator_and_history(self):
        self.complete();self.s.record('blue_cube');self.s.record('red_cube',correct=True)
        self.assertEqual(self.s.statistics(),dict(total=1,correct=1,success_rate=1))
        self.assertEqual(len(self.log.read_text().splitlines()),2)
    def test_restart_recovers_unique_labels(self):
        self.complete();self.s.record('red_cube');restored=ManualSession(self.log)
        self.assertEqual(restored.statistics()['total'],1)
    def test_different_model_statistics_are_not_mixed(self):
        self.complete();self.s.record('red_cube')
        other=ManualSession(self.log,model_id='new-model')
        self.assertEqual(other.statistics()['total'],0)
        self.assertEqual(ManualSession(self.log).statistics()['total'],1)
    def test_file_changed_after_prediction_cannot_record_stale_label(self):
        self.complete();self.a.write_bytes(b'changed after finish')
        with self.assertRaisesRegex(ValueError,'已改变'):self.s.record('red_cube')
    def test_storage_failure_does_not_increment_counter(self):
        self.complete()
        original_open=Path.open
        def fail_log(path,*args,**kwargs):
            if path==self.log:raise OSError('disk fixture')
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',autospec=True,side_effect=fail_log),self.assertRaises(OSError):self.s.record('red_cube')
        self.assertEqual(self.s.statistics()['total'],0)

if __name__=='__main__':unittest.main()
