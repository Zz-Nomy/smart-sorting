from vision_model import *
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from PIL import Image,ImageTk
import threading
import csv

def main():
    root=tk.Tk();root.title('双视图物体识别 · 演示原型');root.geometry('1000x900')
    ttk.Label(root,text='选择同一物体的顶视图与侧视图',font=('Microsoft YaHei',18)).pack(pady=12)
    ttk.Label(root,text='支持：红/蓝 × 立方体、圆柱、圆锥、多棱柱；高分不代表能够识别未知类别').pack()
    ttk.Label(root,text='两图须先确认属于同一实物；当前不验证实例配对，候选结果不能直接驱动分拣').pack()
    frame=ttk.Frame(root);frame.pack(fill='x',padx=20,pady=15)
    paths={};photos={};labels={}
    def choose(view):
        p=filedialog.askopenfilename(filetypes=[('图片','*.jpg *.jpeg *.png *.bmp'),('所有文件','*.*')])
        if not p:return
        paths[view]=p;im=Image.open(p).convert('RGB');im.thumbnail((410,300));photos[view]=ImageTk.PhotoImage(im);labels[view].configure(image=photos[view],text='')
    for col,(view,title) in enumerate([('top','顶视图'),('side','侧视图')]):
        panel=ttk.Frame(frame);panel.grid(row=0,column=col,padx=10,sticky='nsew');frame.columnconfigure(col,weight=1)
        ttk.Button(panel,text='选择'+title,command=lambda v=view:choose(v)).pack(pady=8)
        labels[view]=ttk.Label(panel,text='尚未选择'+title,anchor='center');labels[view].pack(fill='both',expand=True)
    result=tk.Text(root,height=10,font=('Microsoft YaHei',11),wrap='word');result.pack(fill='both',expand=True,padx=20,pady=10)
    result.insert('end','这是现有样件的初步演示模型，尚未经独立实物测试。\n顶视图需尽量垂直拍摄，侧视图应显露侧面；每张只放一个物体，主体完整且背景与物体颜色有区别。\n')
    model=Recognizer();last={};session=[]
    controls=ttk.Frame(root);controls.pack(pady=4)
    ttk.Label(controls,text='真值（人工确认后记录）：').grid(row=0,column=0)
    truth_color=ttk.Combobox(controls,values=['red','blue'],width=8,state='readonly');truth_color.set('red');truth_color.grid(row=0,column=1)
    truth_shape=ttk.Combobox(controls,values=model.shapes,width=12,state='readonly');truth_shape.set(model.shapes[0]);truth_shape.grid(row=0,column=2)
    accuracy=tk.StringVar(value='本次人工核验：0 对；成功率尚无数据（需真值）')
    ttk.Label(root,textvariable=accuracy).pack()
    def record():
        if not last or last.get('recorded'):messagebox.showinfo('提示','请先完成一次新的识别，再记录真值');return
        expected=truth_color.get()+'_'+truth_shape.get();out=last.get('result')
        success=accepted_match(out,expected)
        row=dict(top=last['top'],side=last['side'],expected=expected,predicted=out['class_name'] if out else '__error__',status=out['status'] if out else 'error',success=int(success))
        log=ROOT/'manual_evaluation.csv';exists=log.exists()
        with log.open('a',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(row))
            if not exists:writer.writeheader()
            writer.writerow(row)
        last['recorded']=True;session.append(row);n=sum(r['success'] for r in session)
        accuracy.set(f'本次人工核验：{len(session)} 对；正确 {n} 对；成功率 {n/len(session):.1%}（颜色＋形状同时正确且无需复核）')
    ttk.Button(controls,text='记录该次真值',command=record).grid(row=0,column=3,padx=8)
    def run():
        if not all(v in paths for v in ['top','side']):messagebox.showinfo('缺少图片','请选择两张图片');return
        button.configure(state='disabled');current=dict(paths)
        def work():
            try:
                out=model.predict(current['top'],current['side']);text=f'候选分类：{out["label"]}\n模型分数：{out["score"]:.1%}（未校准，不是正确概率）\n状态：'+('需复核' if out['issues'] else '已输出候选结果')+'\n'
                text+='\n形状排序：\n'+''.join(f'  {v["name"]}  {v["score"]:.1%}\n' for v in out['alternatives'])
                if out['issues']:text+='\n提示：'+'；'.join(out['issues'])
                text+='\n配对状态：未自动验证；本结果不能直接作为机械执行指令。'
                (ROOT/'last_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception as e:out=None;text='识别失败：'+str(e)
            def done():
                last.clear();last.update(top=current['top'],side=current['side'],result=out,recorded=False)
                result.delete('1.0','end');result.insert('end',text);button.configure(state='normal')
            root.after(0,done)
        threading.Thread(target=work,daemon=True).start()
    button=ttk.Button(root,text='识别并分类',command=run);button.pack(pady=10)
    root.mainloop()

if __name__=='__main__':main()
