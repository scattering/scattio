import h5py
from h5py._hl.base import DictCompat
from h5py._hl.dataset import Dataset

def group_dir(self):
    attrs = ['A'+str(s) for s in self.attrs.keys()] if hasattr(self,'attrs') else []
    fields = ['F'+str(s) for s in self.keys()]
    return attrs + fields + dir(self.__class__)

def group_getattr(self, key):
    if key[0]=='A': 
        return self.attrs[key[1:]]
    elif key[0]=='F':
        return self[key[1:]]
    else:
        raise AttributeError('%r object has not attribute %r'
                             %(self.__class__.__name__,key))

def data_dir(self):
    attrs = ['A'+str(s) for s in self.attrs.keys()]
    return attrs + dir(self.__class__)

def data_getattr(self, key):
    if key[0] == 'A':
        return self.attrs[key[1:]]
    else:
        raise AttributeError('%r object has not attribute %r'
                             %(self.__class__.__name__,key))

DictCompat.__dir__ = group_dir
DictCompat.__getattr__ = group_getattr
Dataset.__dir__ = data_dir
Dataset.__getattr__ = data_getattr
