"""Synthetic control-flow fixture only: prove training never reads sealed test images."""
import sys,unittest,tempfile,csv,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
import train
from dataset_contract import REQUIRED

class DummyBackbone(train.torch.nn.Module):
    def forward(self,x):return train.torch.ones((len(x),576),device=x.device)

class SealTests(unittest.TestCase):
    def test_paired_training_seals_test_and_saves_configured_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            for i,(split,shape) in enumerate([('train','cube'),('train','cone'),('val','cube'),('test','cone')]):
                for view in ['top','side']:(root/f'{i}_{view}.jpg').write_bytes(b'not a photo: control-flow fixture')
                rows.append(dict(pair_id=f'p{i}',physical_object_id=f'o{i}',session_id=split,split=split,top=f'{i}_top.jpg',side=f'{i}_side.jpg',color='red',shape=shape,source_kind='real',top_parent_id=f'{i}t',side_parent_id=f'{i}s'))
            manifest=root/'pairs.csv'
            with manifest.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=sorted(REQUIRED));writer.writeheader();writer.writerows(rows)
            shapes=root/'shapes.json';shapes.write_text('["cone","cube"]')
            reads=[]
            def fake_read(path):
                self.assertFalse(Path(path).name.startswith('3_'),'sealed test image was read')
                reads.append(path);return path
            argv=['train','--pairs',str(manifest),'--shapes',str(shapes),'--output',str(root/'run'),'--cache',str(root/'cache'),'--steps','1']
            with patch.object(sys,'argv',argv),patch.object(train,'read',side_effect=fake_read),patch.object(train,'preprocess',return_value=(train.torch.zeros(3,224,224),{})),patch.object(train,'mobilenet_v3_small',return_value=DummyBackbone()):train.main()
            metrics=json.loads((root/'run/metrics.json').read_text())
            self.assertEqual(len(reads),6);self.assertEqual(metrics['test_pairs_sealed'],1)
            self.assertEqual(metrics['shapes'],['cone','cube'])
            self.assertEqual(metrics['features_extracted_images'],6)
            pack=train.torch.load(root/'run/model.pt',map_location='cpu')
            self.assertEqual(pack['shapes'],['cone','cube']);self.assertEqual(tuple(pack['weight'].shape),(2,1152))
    def test_legacy_requires_explicit_opt_in_before_reading_data(self):
        with patch.object(sys,'argv',['train','--data','missing-dataset']),self.assertRaises(SystemExit) as result:train.main()
        self.assertEqual(result.exception.code,2)

if __name__=='__main__':unittest.main()
