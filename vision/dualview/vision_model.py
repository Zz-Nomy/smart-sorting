from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
for ancestor in ROOT.parents:
    runtime=ancestor/'work'/'vision_runtime'
    if runtime.is_dir():sys.path.insert(0,str(runtime));break
import numpy as np,cv2,torch,json
from torchvision.models import mobilenet_v3_small
torch.set_num_threads(4)
SHAPES=['cube','cylinder','cone','prism']
ZH={'cube':'立方体','cylinder':'圆柱','cone':'圆锥','prism':'多棱柱','red':'红色','blue':'蓝色','unknown':'未知颜色'}

def accepted_match(result,expected):
    return result is not None and result['status']=='candidate' and result['class_name']==expected

def read(path):
    im=cv2.imdecode(np.fromfile(str(path),np.uint8),1)
    if im is None:raise ValueError('无法读取图片：'+str(path))
    return im

def locate(im):
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    red=cv2.inRange(hsv,(0,80,25),(15,255,255))|cv2.inRange(hsv,(160,80,25),(179,255,255))
    blue=cv2.inRange(hsv,(85,80,20),(140,255,255))
    mask=red|blue
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    h,w=im.shape[:2];cs=[c for c in cs if cv2.contourArea(c)>h*w*.001]
    if not cs:raise ValueError('未找到支持的红/蓝单目标，请检查图片或扩展训练类别')
    cs.sort(key=cv2.contourArea,reverse=True)
    if len(cs)>1 and cv2.contourArea(cs[1])>cv2.contourArea(cs[0])*.10:
        raise ValueError('检测到多个显著目标；当前原型不支持跨视图自动匹配，请先裁出同一物体')
    c=cs[0];x,y,bw,bh=cv2.boundingRect(c)
    if bw<12 or bh<12:raise ValueError('目标太小')
    fg=np.zeros((h,w),np.uint8);cv2.drawContours(fg,[c],-1,255,-1)
    nr=np.count_nonzero((red>0)&(fg>0));nb=np.count_nonzero((blue>0)&(fg>0));color='red' if nr>=nb else 'blue'
    return (x,y,x+bw,y+bh),fg,color,max(nr,nb)/max(nr+nb,1)

def preprocess(im,box=None):
    auto,mask,color,purity=locate(im)
    if box is None:box=auto
    x1,y1,x2,y2=[int(v) for v in box];h,w=im.shape[:2]
    # Isolate the target and remove background/lighting cues from shape features.
    gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    gray=np.where(mask>0,gray,180).astype(np.uint8)
    pad=max(5,int(max(x2-x1,y2-y1)*.12))
    crop=gray[max(0,y1-pad):min(h,y2+pad),max(0,x1-pad):min(w,x2+pad)]
    size=max(crop.shape);canvas=np.full((size,size),180,np.uint8);oy=(size-crop.shape[0])//2;ox=(size-crop.shape[1])//2
    canvas[oy:oy+crop.shape[0],ox:ox+crop.shape[1]]=crop
    arr=cv2.resize(canvas,(224,224)).astype(np.float32)/255
    arr=np.repeat(arr[None,:,:],3,axis=0)
    arr=(arr-np.array([.485,.456,.406],np.float32)[:,None,None])/np.array([.229,.224,.225],np.float32)[:,None,None]
    return torch.from_numpy(arr),dict(bbox=list(auto),color=color,color_purity=round(float(purity),4),touches_edge=auto[0]<2 or auto[1]<2 or auto[2]>w-2 or auto[3]>h-2)

class Recognizer:
    def __init__(self,checkpoint=None,device='cpu'):
        self.device=torch.device(device)
        pack=torch.load(checkpoint or ROOT/'model.pt',map_location='cpu')
        self.net=mobilenet_v3_small(weights=None);self.net.classifier=torch.nn.Identity();self.net.load_state_dict(pack['backbone']);self.net.eval().to(self.device)
        self.mean=pack['mean'].to(self.device);self.std=pack['std'].to(self.device)
        self.weight=pack['weight'].to(self.device);self.bias=pack['bias'].to(self.device)
    @torch.inference_mode()
    def predict(self,top,side):
        a,ma=preprocess(read(top));b,mb=preprocess(read(side))
        feat=self.net(torch.stack([a,b]).to(self.device)).reshape(1,-1)
        logits=((feat-self.mean)/self.std)@self.weight.T+self.bias
        p=torch.softmax(logits,dim=1)[0].cpu().tolist();order=sorted(range(4),key=lambda i:p[i],reverse=True)
        idx=order[0];score=p[idx];margin=score-p[order[1]]
        issues=[]
        if ma['color']!=mb['color']:issues.append('两视图颜色不一致，请确认同一物体')
        if min(ma['color_purity'],mb['color_purity'])<.85:issues.append('目标颜色混杂')
        if ma['touches_edge'] or mb['touches_edge']:issues.append('目标触及图像边缘')
        if score<.75 or margin<.3:issues.append('形状分数不足，建议重新拍摄或人工复核')
        color=ma['color'] if ma['color']==mb['color'] else 'unknown'
        return dict(status='needs_review' if issues else 'candidate',class_name=color+'_'+SHAPES[idx],label=ZH[color]+ZH[SHAPES[idx]],shape=SHAPES[idx],color=color,score=round(score,4),score_note='未校准的闭集模型分数，并非正确概率；高分也不能排除未知类别',alternatives=[dict(shape=SHAPES[i],name=ZH[SHAPES[i]],score=round(p[i],4)) for i in order],issues=issues,top=ma,side=mb)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--top',required=True);ap.add_argument('--side',required=True);ap.add_argument('--json');ap.add_argument('--checkpoint');args=ap.parse_args()
    result=Recognizer(args.checkpoint).predict(args.top,args.side);s=json.dumps(result,ensure_ascii=False,indent=2);print(s)
    if args.json:Path(args.json).write_text(s,encoding='utf-8')
