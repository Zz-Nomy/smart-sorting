"""Failures that would silently inflate evaluation are rejected before model loading."""
import sys,unittest,csv,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
from dataset_contract import load_pairs,validate_shapes,REQUIRED

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.csv=self.root/'pairs.csv';self.rows=[]
        for i,(split,shape) in enumerate([('train','cube'),('train','cone'),('val','cube'),('val','cone'),('test','cube')]):
            for view in ['top','side']:(self.root/f'{i}_{view}.jpg').write_bytes(b'existence fixture, not a real photograph')
            self.rows.append(dict(pair_id=f'p{i}',physical_object_id=f'obj{i}',session_id=split,split=split,top=f'{i}_top.jpg',side=f'{i}_side.jpg',color='red',shape=shape,source_kind='real',top_parent_id=f'{i}t',side_parent_id=f'{i}s'))
    def load(self):
        with self.csv.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=sorted(REQUIRED));w.writeheader();w.writerows(self.rows)
        return load_pairs(self.csv,['cube','cone'])
    def test_valid_grouped_manifest_and_sealed_test(self):
        rows=self.load();self.assertEqual(len(rows),5);self.assertEqual(rows[-1]['split'],'test')
        self.assertTrue(Path(rows[0]['top']).is_absolute())
    def test_same_object_different_sessions_leaks(self):
        self.rows[2]['physical_object_id']='obj0'
        with self.assertRaisesRegex(ValueError,'cross-split.*object'):self.load()
    def test_shared_session_across_different_objects_leaks(self):
        self.rows[2]['session_id']='train'
        with self.assertRaisesRegex(ValueError,'cross-split.*session'):self.load()
    def test_augmentation_parent_cannot_enter_validation(self):
        self.rows[2]['top_parent_id']='0t'
        with self.assertRaisesRegex(ValueError,'cross-split.*parent'):self.load()
    def test_same_image_with_renamed_parent_still_leaks(self):
        self.rows[2]['top']='0_top.jpg'
        with self.assertRaisesRegex(ValueError,'cross-split.*image'):self.load()
    def test_derived_validation_rejected(self):
        self.rows[2]['source_kind']='derived'
        with self.assertRaisesRegex(ValueError,'must be real'):self.load()
    def test_missing_image_does_not_silently_drop_sample(self):
        self.rows[0]['top']='missing.jpg'
        with self.assertRaisesRegex(ValueError,'missing top'):self.load()
    def test_same_physical_object_cannot_change_label(self):
        self.rows[1]['physical_object_id']='obj0'
        with self.assertRaisesRegex(ValueError,'inconsistent truth'):self.load()
    def test_all_configured_shapes_need_training_examples(self):
        self.rows[1]['shape']='cube'
        with self.assertRaisesRegex(ValueError,'cover all'):self.load()
    def test_duplicate_pairs_rejected_even_with_new_id(self):
        self.rows[1]['top']=self.rows[0]['top'];self.rows[1]['side']=self.rows[0]['side']
        with self.assertRaisesRegex(ValueError,'duplicate image pair'):self.load()
    def test_invalid_label_schema_rejected(self):
        for shapes in [[],['cube','cube'],['cube',{}],['cube','']]:
            with self.subTest(shapes=shapes),self.assertRaises(ValueError):validate_shapes(shapes)

if __name__=='__main__':unittest.main()
