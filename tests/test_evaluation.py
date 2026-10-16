import sys,unittest,tempfile,csv
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
import evaluate as ev

def result(truth='red_cube',predicted='red_cube',outcome='success',known=True):
    accepted=outcome in {'success','wrong_accept'}
    return dict(expected=truth,predicted=predicted,known_truth=known,accepted=accepted,
                success=outcome=='success',outcome=outcome,color_error=False,shape_error=predicted!=truth,
                failure_reasons=[] if outcome=='success' else [outcome])

class EvaluationTests(unittest.TestCase):
    def test_success_precision_coverage_have_different_denominators(self):
        rows=[result() for _ in range(90)]+[result(predicted='red_cone',outcome='wrong_accept') for _ in range(3)]+[result(predicted='__review__',outcome='review') for _ in range(7)]
        stats=ev.summarize(rows)
        self.assertEqual(stats['success_rate'],.9);self.assertEqual(stats['acceptance_coverage'],.93)
        self.assertAlmostEqual(stats['accepted_precision'],90/93)
    def test_zero_acceptance_precision_is_undefined_not_perfect(self):
        stats=ev.summarize([result(outcome='review')])
        self.assertIsNone(stats['accepted_precision']);self.assertEqual(stats['success_rate'],0)
    def test_unknown_reject_is_separate_from_classification_success(self):
        stats=ev.summarize([result(truth='green_cube',outcome='review',known=False)])
        self.assertEqual(stats['unknown_false_accept_rate'],0);self.assertEqual(stats['correct'],0)
        self.assertIsNone(stats['known_success_rate'])
    def test_evaluator_counts_wrong_color_shape_missing_review_and_unknown(self):
        calls=[]
        class FakeModel:
            shapes=['cube','cone']
            def __init__(self,*args):pass
            def predict(self,top,side):
                calls.append(top);key=Path(top).stem
                if key=='missing':raise FileNotFoundError('fixture missing image')
                color='blue' if key=='wrongcolor' else 'red';shape='cone' if key=='wrongshape' else 'cube'
                return dict(status='needs_review' if key=='review' else 'candidate',class_name=color+'_'+shape,color=color,shape=shape,issues=['low_quality'] if key=='review' else [])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pairs.csv'
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['top','side','color','shape']);writer.writeheader()
                for key in ['ok','wrongcolor','wrongshape','review','missing','unknown']:
                    writer.writerow(dict(top=key+'.jpg',side=key+'_side.jpg',color='green' if key=='unknown' else 'red',shape='cube'))
            with patch.object(ev,'Recognizer',FakeModel):report=ev.evaluate(path,warmup=2)
        self.assertEqual(report['total'],6);self.assertEqual(report['correct'],1);self.assertEqual(report['errors'],1)
        self.assertEqual(report['accepted'],4);self.assertEqual(report['accepted_precision'],.25)
        self.assertEqual(report['known_success_rate'],.2);self.assertEqual(report['unknown_false_accept_rate'],1)
        self.assertEqual(report['failure_reasons']['wrong_color'],2)
        self.assertEqual(report['failure_reasons']['wrong_shape'],1)
        self.assertEqual(report['per_class']['red_cube']['input_errors'],1)
        self.assertEqual(len(calls),8);self.assertEqual(len(report['results']),6)
    def test_duplicate_path_alias_and_reversed_views_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pairs.csv'
            path.write_text('top,side,color,shape\na.jpg,b.jpg,red,cube\n./b.jpg,./a.jpg,red,cube\n')
            with self.assertRaisesRegex(ValueError,'Duplicate image pair'):ev.load_evaluation_rows(path)
    def test_invalid_metadata_fails_before_loading_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pairs.csv';path.write_text('top,side,color,shape\na.jpg,b.jpg,,cube\n')
            with patch.object(ev,'Recognizer') as model,self.assertRaises(ValueError):ev.evaluate(path)
            model.assert_not_called()

if __name__=='__main__':unittest.main()
