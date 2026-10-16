import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
from vision_model import np,cv2,locate,accepted_match

class DualViewTests(unittest.TestCase):
    def test_joint_success_requires_color_and_shape(self):
        p=dict(status='candidate',class_name='red_cube')
        self.assertTrue(accepted_match(p,'red_cube'))
        self.assertFalse(accepted_match(p,'blue_cube'))
        self.assertFalse(accepted_match(p,'red_cone'))
        self.assertFalse(accepted_match(dict(p,status='needs_review'),'red_cube'))
        self.assertFalse(accepted_match(None,'red_cube'))
    def test_empty_background_is_not_classified(self):
        image=np.zeros((240,320,3),np.uint8);image[:,:,1]=255
        with self.assertRaisesRegex(ValueError,'未找到'):locate(image)
    def test_off_center_target_is_located(self):
        image=np.full((240,320,3),170,np.uint8);image[20:75,230:285]=[0,0,180]
        box,_,color,_=locate(image)
        self.assertEqual(color,'red');self.assertEqual(box,(230,20,285,75))
    def test_multiple_targets_require_pairing(self):
        image=np.full((240,320,3),170,np.uint8);image[20:75,30:85]=[0,0,180];image[120:190,200:270]=[180,0,0]
        with self.assertRaisesRegex(ValueError,'多个'):locate(image)

if __name__=='__main__':unittest.main()
