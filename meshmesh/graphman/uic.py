import os
import sys

def pyside_uic_version():
    return "UIC auto-generator version 1.1"


def _pyside2_uic(path, uic):
    for f in os.listdir(path):
        f_path = os.path.join(path, f)
        if os.path.isdir(f_path) and f[0] != '.' and f != 'venv':
            _pyside2_uic(f_path, uic)
        else:
            b, e = os.path.splitext(f)
            if e == '.ui':
                d_path = '{}/{}_ui.py'.format(path, b)
                if not os.path.exists(d_path) or os.path.getctime(f_path) >= os.path.getctime(d_path):
                    cmd = '{} {} -o {}'.format(uic, f_path, d_path)
                    print(cmd)
                    os.system(cmd)


def pyside_uic():
    print('Check there are new UI files...')
    uic_path = os.path.join(os.path.dirname(sys.executable), 'pyside6-uic')
    c_path = os.path.dirname(os.path.realpath(__file__))
    _pyside2_uic(c_path, uic_path)
    print('... UI file build completed')


pyside_uic()
