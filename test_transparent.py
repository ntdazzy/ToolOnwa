import tkinter as tk
root=tk.Tk()
root.geometry('200x100')
tree=tk.Label(root,text='Hello',bg='yellow')
tree.pack(fill='both',expand=True)
canvas=tk.Canvas(tree,bg='SystemButtonFace',highlightthickness=0)
canvas.place(relx=0,rely=0,relwidth=1,relheight=1)
root.after(2000, root.destroy)
root.mainloop()
