import os


for file in os.listdir(os.getcwd()):
    if file.endswith('.ui'):
        base = file[:-3]
        source = file
        target = 'ui_' + base + '.py'
        if not os.path.exists(target) or os.path.getmtime(source) > os.path.getmtime(target):
            print(file)
            cmd = 'pyside2-uic %s -o %s' % (source, target)
            print(cmd)
            os.system(cmd)
