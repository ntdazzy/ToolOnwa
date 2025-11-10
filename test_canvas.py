import tkinter as tk
root=tk.Tk();root.geometry('200x200')
frame=tk.Frame(root)
frame.pack(fill='both',expand=True)
label=tk.Label(frame,text='Hello world',bg='white')
label.pack(fill='both',expand=True)
canvas=tk.Canvas(frame,bg='')
canvas.place(relx=0,rely=0,relwidth=1,relheight=1)
root.after(2000, root.destroy)
try:
    print('bg repr',canvas.cget('bg'))
except Exception as e:
    print('error',e)
root.mainloop()
