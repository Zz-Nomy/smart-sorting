from vision_model import *
from manual_session import ManualSession
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from PIL import Image,ImageTk
import threading,queue,argparse

class DemoApp:
    def __init__(self,root,model=None,log_path=None):
        self.root=root;self.model=model or Recognizer();self.session=ManualSession(log_path or ROOT/'manual_evaluation.jsonl',model_id=getattr(self.model,'model_sha256','unspecified'))
        self.messages=queue.Queue();self.closed=False;self.photos={};self.labels={};self.select_buttons=[]
        root.title('双视图物体识别 演示原型');root.geometry('1000x900')
        ttk.Label(root,text='选择同一物体的顶视图与侧视图',font=('Microsoft YaHei',18)).pack(pady=12)
        ttk.Label(root,text='仅红蓝与已训练形状；配对未经自动验证，候选不能直接驱动分拣').pack()
        panel=ttk.Frame(root);panel.pack(fill='x',padx=20,pady=10)
        for col,(view,title) in enumerate([('top','顶视图'),('side','侧视图')]):
            frame=ttk.Frame(panel);frame.grid(row=0,column=col,padx=10,sticky='nsew');panel.columnconfigure(col,weight=1)
            button=ttk.Button(frame,text='选择'+title,command=lambda v=view:self.choose(v));button.pack(pady=8);self.select_buttons.append(button)
            self.labels[view]=ttk.Label(frame,text='尚未选择'+title,anchor='center');self.labels[view].pack(fill='both',expand=True)
        self.result=tk.Text(root,height=10,font=('Microsoft YaHei',11),wrap='word');self.result.pack(fill='both',expand=True,padx=20,pady=10)
        self.show('这是已知样件演示；未知类别、多目标自动配对与独立实物稳定性尚未验收。')
        controls=ttk.Frame(root);controls.pack(pady=6)
        ttk.Label(controls,text='人工真值').grid(row=0,column=0)
        self.color=ttk.Combobox(controls,values=['red','blue'],width=8,state='readonly');self.color.set('red');self.color.grid(row=0,column=1)
        self.shape=ttk.Combobox(controls,values=self.model.shapes,width=12,state='readonly');self.shape.set(self.model.shapes[0]);self.shape.grid(row=0,column=2)
        self.confirmed=tk.BooleanVar(value=False)
        ttk.Checkbutton(root,text='我已确认两图属于同一实物，且人工真值正确',variable=self.confirmed).pack()
        self.record_button=ttk.Button(controls,text='记录唯一图片对',command=lambda:self.record(False));self.record_button.grid(row=0,column=3,padx=6)
        self.correct_button=ttk.Button(controls,text='更正这对真值',command=lambda:self.record(True));self.correct_button.grid(row=0,column=4,padx=6)
        self.accuracy=tk.StringVar();ttk.Label(root,textvariable=self.accuracy).pack(pady=5)
        ttk.Label(root,text='按文件内容去重，不代表独立实物；更正保留历史，旧CSV不自动混入').pack()
        self.run_button=ttk.Button(root,text='识别并分类',command=self.start);self.run_button.pack(pady=10)
        self.show_stats();self.set_busy(False);root.protocol('WM_DELETE_WINDOW',self.close);root.after(50,self.poll)
    def show(self,text):self.result.delete('1.0','end');self.result.insert('end',text)
    def show_stats(self):
        stats=self.session.statistics();rate=f'{stats["success_rate"]:.1%}' if stats['total'] else '尚无数据'
        self.accuracy.set(f'当前权重累计唯一图片对：{stats["total"]} 对；正确 {stats["correct"]} 对；成功率 {rate}')
    def set_busy(self,busy):
        for button in self.select_buttons+[self.run_button]:button.configure(state='disabled' if busy else 'normal')
        state='normal' if not busy and self.session.current is not None else 'disabled'
        self.record_button.configure(state=state);self.correct_button.configure(state=state)
        self.color.configure(state='disabled' if busy else 'readonly');self.shape.configure(state='disabled' if busy else 'readonly')
    def choose(self,view,path=None):
        if self.session.busy:return
        path=path or filedialog.askopenfilename(filetypes=[('图片','*.jpg *.jpeg *.png *.bmp'),('所有文件','*.*')])
        if not path:return
        try:
            with Image.open(path) as source:image=source.convert('RGB')
            image.thumbnail((410,270));photo=ImageTk.PhotoImage(image)
            self.session.select(view,path);self.photos[view]=photo;self.labels[view].configure(image=photo,text='')
            self.confirmed.set(False);self.show('图片已更新，请重新识别后确认真值。');self.set_busy(False)
        except (OSError,ValueError) as error:messagebox.showerror('图片读取失败',str(error))
    def start(self):
        try:job,paths=self.session.start()
        except ValueError as error:messagebox.showinfo('提示',str(error));return
        self.confirmed.set(False);self.set_busy(True);self.show('正在识别；完成前不能记录旧结果或切换图片。')
        def work():
            try:out=self.model.predict(paths['top'],paths['side']);error=None
            except Exception as exc:out=None;error=str(exc)
            self.messages.put((job,out,error))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        if self.closed:return
        while not self.messages.empty():
            job,out,error=self.messages.get_nowait()
            if not self.session.finish(job,out,error):continue
            current=self.session.current;out=current['result'];error=current['error']
            if out:
                text=f'候选分类：{out["label"]}\n模型分数：{out["score"]:.1%}（未校准，不是正确概率）\n'
                text+='状态：'+('需复核' if out['status']!='candidate' else '候选分类已输出')+'\n'
                text+='\n'.join(f'{v["name"]}  {v["score"]:.1%}' for v in out['alternatives'])
                if out['issues']:text+='\n提示：'+'；'.join(out['issues'])
                text+='\n配对未经自动验证，不能直接作为机械执行指令。'
            else:text='识别失败：'+str(error)+'\n确认真值后可将本次失败记入分母。'
            self.show(text);self.set_busy(False)
            try:(ROOT/'last_result.json').write_text(json.dumps(dict(result=out,error=error),ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError:self.show(text+'\n结果快照未能保存；请检查目录写权限。')
        self.root.after(50,self.poll)
    def record(self,correct=False):
        if not self.confirmed.get():messagebox.showinfo('确认真值','请先确认两图对应关系及人工真值');return
        try:self.session.record(self.color.get()+'_'+self.shape.get(),correct=correct)
        except (ValueError,OSError) as error:messagebox.showinfo('未记录',str(error));return
        self.show_stats()
    def close(self):self.closed=True;self.root.destroy()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checkpoint');args=ap.parse_args()
    root=tk.Tk()
    try:DemoApp(root,model=Recognizer(args.checkpoint))
    except Exception as error:messagebox.showerror('启动失败',str(error));root.destroy();return
    root.mainloop()

if __name__=='__main__':main()
