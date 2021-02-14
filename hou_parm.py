# The MetaHouParm and HouParm class..

import os
import re
import hou
 
class MetaHouParm(type):
    """
    The MetaHouParm class is a metaclass that keeps track of which
    classes support which parameter types.
    """
    PARM_TYPE_TO_CLASS = dict()
    
    def __new__(cls, class_name, bases, class_dict):
        """
        Called when a class is created that uses this metaclass
        """
        # create the new class
        new_cls = type.__new__(cls, class_name, bases, class_dict)
        
        supported_parm_types = class_dict.get('SUPPORTED_TYPES', [])
        for parm_type in supported_parm_types:
            cls.PARM_TYPE_TO_CLASS[parm_type] = new_cls
        return new_cls
        
    @classmethod
    def get_node_parm(mcls, hou_node, parm_name):
        """
        Instantiates and returns a HouParm object
        to represent the specified node paramter.
        """
        sesi_tuple = hou_node.parmTuple(parm_name)
        if sesi_tuple and len(sesi_tuple) > 1:
            parm_template = sesi_tuple.parmTemplate()
            return NodeParmTuple(hou_node, parm_name,
                                 parm_template, sesi_tuple)
            
        sesi_parm = hou_node.parm(parm_name)
        if not sesi_parm:
            return None
        parm_template = sesi_parm.parmTemplate()
        parm_type = parm_template.type()
        cls = mcls.PARM_TYPE_TO_CLASS.get(parm_type, HouParm)
        cls = cls.get_class_for_parm(parm_template)
        return cls(hou_node, parm_name, parm_template, sesi_parm)
    
class HouParm(object):
    """
    The base class to represent a Houdini node parameter.
    """
    __metaclass__ = MetaHouParm
    SUPPORTED_TYPES = []
    CAST_TYPE = None
    def __init__(self, hou_node, parm_name,
                 parm_template, sesi_parm=None):
        """
        Initializer for a Node parameter.
        """
        self._hou_node = hou_node
        self._parm_name = parm_name
        self._parm_template = parm_template
        self._sesi_parm = sesi_parm
        self._cast_type = None
        
        self._parm_method_names = []
        self.update_node_methods()
    
    @classmethod
    def get_class_for_parm(cls, parm_template):
        """
        Virtual method to control what HouParm class gets used
        for the specified parmater template. After the class is identied
        by the SUPPORTED_TYPES list.
        """
        return cls

    def update_node_methods(self, parm_method_names=None):
        """
        Updates the list of SESI parm method names
        that can be called vicariously on this HouParm instance.
        """    
        if parm_method_names == None:
            parm_method_names = dir(self._sesi_parm)
        self._parm_method_names = parm_method_names

    def __getattr__(self, key):
        """
        Overrides the attribute retrieval method for HouParm instances.
        This method is only called if a python attribute or method of the
        requested name was not found.
        """
            
        # check for a method on the parm tuple for the requested attribute name
        #
        if not key.startswith('_'):
            method_names = self.__dict__.get('_parm_method_names', None)
            sesi_parm = self.__dict__.get('_sesi_parm', None)
            if sesi_parm and method_names and key in method_names:
                return getattr(sesi_parm, key)
        
        # no valid attribute could be found
        raise AttributeError('Unknown attribute "%s"' % key)
                
    def get_value(self):
        """
        Returns the value stored by this parameter object.
        """
        return self._sesi_parm.eval()

    def set_value(self, value):
        """
        Sets the value stored by this parameter object.
        """
        print value
        if self.CAST_TYPE:
            value = self.CAST_TYPE(value)
        self._sesi_parm.set(value)
        
    def __nonzero__(self):
        """
        Handles cast to boolean.
        """
        return bool(self.eval())

    def __float__(self):
        """
        Handles cast to float.
        """
        return self.evalAsFloat()
        
    def __int__(self):
        """
        Handles cast to integer.
        """
        return self.evalAsInt()

    def __str__(self):
        """
        Handles cast to string.
        """
        return self.evalAsString()

    def __unicode(self):
        """
        Handles cast to unicode.
        """
        return unicode(self.evalAsString())
        
    def __coerce__(self, other):
        """
        Handles cast to string.
        """
        if other == None:
            return (True, None)
        # coercion to primitive types
        #
        if isinstance(other, float):
            return (float(self), other)
        if isinstance(other, int):
            return (int(self), other)
        if isinstance(other, bool):
            return (bool(self), other)
        if isinstance(other, str):
            return (str(self), other)
        if isinstance(other, unicode):
            return (unicode(self), other)
        # coercion between parm objects
        #
        if isinstance(other, FloatNodeParm):
            return (float(self), float(other))
        if isinstance(other, IntNodeParm):
            return (int(self), int(other))
        if isinstance(other, ToggleNodeParm):
            return (bool(self), bool(other))
        if isinstance(other, MenuNodeParm):
            return (str(self), str(other))
        if isinstance(other, StringNodeParm):
            return (str(self), str(other))
        if isinstance(other, HouParm):
            return (id(self), id(other))
        # unknown type to coerce to
        return (self, False)

    def __repr__(self):
        return '<%s path "%s" value "%s" at %d>' % (self.__class__.__name__,
                                                    self._sesi_parm.path(),
                                                    str(self.get_value()), id(self))

class NodeParmTuple(object):
    """
    This class represents a multi-parm tuple
    on a HouNode (e.g. t,r,s on a geo node).
    """
    def __init__(self, hou_node, tuple_name,
                 parm_template, sesi_parm_tuple):
        """
        Initializer for a Node parameter tuple.
        """
        self._hou_node = hou_node
        self._tuple_name = tuple_name
        self._parm_template = parm_template
        self._sesi_parm_tuple = sesi_parm_tuple
        
        self._tuple_method_names = []
        self._sub_parms = [hou_node.get_node_parm(parm.name()) 
                           for parm in sesi_parm_tuple]
        self.update_parm_methods()

    def update_parm_methods(self, parm_method_names=None):
        """
        Updates the list of SESI parm tuple method names
        that can be called vicariously on a NodeParmTuple instance.
        """    
        if parm_method_names == None:
            parm_method_names = dir(self._sesi_parm_tuple)
        self._parm_method_names = parm_method_names
     
    def get_value(self):
        return self._sesi_parm_tuple.eval()
     
    def set_value(self, *args):
        if len(args) == 1:
            args = args[0]
            if isinstance(args, NodeParmTuple):
                args = args.get_value()
        return self._sesi_parm_tuple.set(*args)
     
    def __len__(self):
        return len(self._sub_parms)

    def __getitem__(self, index):
        return self._sub_parms[index]
        
    def __setitem__(self, index, value):
        return self._sub_parms[index].set_value(value)
        
    def __iter__(self, index):
        return iter(self._sub_parms)

    def __repr__(self):
        path = '%s/%s' % (self._hou_node.path(), self._tuple_name)
        return '<%s path "%s" value "%s" at %d>' % (self.__class__.__name__,
                                                    path, str(self.get_value()),
                                                    id(self))

class NumericNodeParm(HouParm):
    
    # override common math operators
    def __add__(self, other):
        return self.get_value() + self.CAST_TYPE(other)
    def __sub__(self, other):
        return self.get_value() - self.CAST_TYPE(other)
    def __mul__(self, other):
        return self.get_value() * self.CAST_TYPE(other)
    def __floordiv__(self, other):
        return self.get_value() // self.CAST_TYPE(other)
    def __mod__(self, other):
        return self.get_value() % self.CAST_TYPE(other)
    def __pow__(self, other):
        return self.get_value() ** self.CAST_TYPE(other)
    def __lshift__(self, other):
        return self.get_value() << other
    def __rshift__(self, other):
        return self.get_value() >> other
    def __and__(self, other):
        return self.get_value() & self.CAST_TYPE(other)
    def __xor__(self, other):
        return self.get_value() ^ self.CAST_TYPE(other)
    def __or__(self, other):
        return self.get_value() | self.CAST_TYPE(other)
    def __div__(self, other):
        return self.get_value() / self.CAST_TYPE(other)
    def __truediv__(self, other):
        return self.get_value() / self.CAST_TYPE(other)

    # right side operations
    def __radd__(self, other):
        return self.CAST_TYPE(other) + self.get_value()
    def __rsub__(self, other):
        return self.CAST_TYPE(other) - self.get_value()
    def __rmul__(self, other):
        return self.CAST_TYPE(other) * self.get_value()
    def __rdiv__(self, other):
        return self.CAST_TYPE(other) / self.get_value()
    def __rtruediv__(self, other):
        return self.CAST_TYPE(other) / self.get_value()
    def __rfloordiv__(self, other):
        return self.CAST_TYPE(other) // self.get_value()
    def __rmod__(self, other):
        return self.CAST_TYPE(other) % self.get_value()
    def __rpow__(self, other):
        return self.CAST_TYPE(other) ** self.get_value()
    def __rlshift__(self, other):
        return other << self.get_value()
    def __rrshift__(self, other):
        return other >> self.get_value()
    def __rand__(self, other):
        return self.CAST_TYPE(other) & self.get_value()
    def __rxor__(self, other):
        return self.CAST_TYPE(other) ^ self.get_value()
    def __ror__(self, other):
        return self.CAST_TYPE(other) | self.get_value()

    # inplace operations
    def __iadd__(self, other):
        return self.get_value() + self.CAST_TYPE(other)
    def __isub__(self, other):
        return self.get_value() - self.CAST_TYPE(other)
    def __imul__(self, other):
        return self.get_value() * self.CAST_TYPE(other)
    def __idiv__(self, other):
        return self.get_value() / self.CAST_TYPE(other)
    def __itruediv__(self, other):
        return self.get_value() / self.CAST_TYPE(other)
    def __ifloordiv__(self, other):
        return self.get_value() // self.CAST_TYPE(other)
    def __imod__(self, other):
        return self.get_value() % self.CAST_TYPE(other)
    def __ipow__(self, other):
        return self.get_value() ** self.CAST_TYPE(other)
    def __ilshift__(self, other):
        return self.get_value() << other
    def __irshift__(self, other):
        return self.get_value() >> other
    def __iand__(self, other):
        return self.get_value() & self.CAST_TYPE(other)
    def __ixor__(self, other):
        return self.get_value() ^ self.CAST_TYPE(other) 
    def __ior__(self, other):
        return self.get_value() | self.CAST_TYPE(other)
    def __neg__(self):
        return -self.get_value()
    def __pos__(self):
        return +self.get_value()
    def __abs__(self):
        return abs(self.get_value())
    def __invert__(self):
        return ~self.get_value()

class IntNodeParm(NumericNodeParm):
    SUPPORTED_TYPES = [hou.parmTemplateType.Int]
    CAST_TYPE = int
    
class ToggleNodeParm(NumericNodeParm):
    SUPPORTED_TYPES = [hou.parmTemplateType.Toggle]
    CAST_TYPE = bool
    
class FloatNodeParm(NumericNodeParm):
    SUPPORTED_TYPES = [hou.parmTemplateType.Float]
    CAST_TYPE = float
    
class MenuNodeParm(HouParm):
    SUPPORTED_TYPES = [hou.parmTemplateType.Menu]
    
class StringNodeParm(HouParm):
    SUPPORTED_TYPES = [hou.parmTemplateType.String]
    CAST_TYPE = str
    
    @classmethod
    def get_class_for_parm(cls, parm_template):
        """
        Get a HouParm class based on the parameters string type.
        """
        if not isinstance(parm_template, hou.StringParmTemplate):
            raise Exception('Unknown parmeter template type "%s"'
                            % type(parm_template).__name__)
        string_type = parm_template.stringType()
        if string_type == hou.stringParmType.Regular:
            return StringNodeParm
        elif string_type == hou.stringParmType.FileReference:
            return FileReferenceNodeParm
        elif string_type == hou.stringParmType.NodeReference:
            return NodeReferenceParm
        elif string_type == hou.stringParmType.NodeReferenceList:
            return NodeListReferenceParm
        return cls
 
    def expand(self, ignore_frame=False, ignore_names=None):
        """
        Expands expression globals in this string parameter
        optionally ignoring specific global variables.
        """
        self._ignore_frame = ignore_frame
        self._ignore_names = ignore_names
        path = self._sesi_parm.unexpandedString()
        return re.sub(r'\${?([a-zA-Z0-9_]+)}?', self._replace_var, path)
        
    def _replace_var(self, match_obj):
        """
        Replaces global variables in a path except frame place holders.
        """
        original_str = match_obj.group(0)
        var_name = match_obj.group(1)
        if self._ignore_frame and re.match('F[0-9]?$', var_name):
            return original_str
        if self._ignore_names and var_name in self._ignore_names:
            return original_str
        if var_name:
            value, err = hou.hscript('echo $%s' % var_name)
            value = str(value).rstrip('\n')
            if value and not err:
                # remove trailing new line
                return value
        return original_str
        
class FileReferenceNodeParm(StringNodeParm):
    """
    A parameter that references a file or file path.
    """
    def create_directory(self):
        """
        Creates any missing directories in this parameter file path.
        """
        path = self._sesi_parm.evalAsString()
        dir, file = os.path.split(path)
        if '.' in file:
            path = dir
        if not os.path.exists(path):
            os.makedirs(path)
            
    def expand_path(self):
        return self.expand(True)
        
class NodeReferenceParm(StringNodeParm):
    """
    A parameter that references another Houdini node.
    """
    def get_node(self):
        value = self._sesi_parm.evalAsString()
        return hou.node(value)

    def get_hou_node(self):
        from hou_node import get_hou_node
        value = self._sesi_parm.evalAsString()
        return get_hou_node(hou.node(value))
        
class NodeListReferenceParm(StringNodeParm):
    """
    A multiple node reference parameter.
    """
    def get_nodes(self):
        str_value = self._sesi_parm.evalAsString()
        values = str_value.split()
        nodes = []
        for value in values:
            if value.startswith('@'):
                node_bundle = hou.nodeBundle(value)
                if node_bundle != None:
                    nodes.extend(node_bundle.nodes())
            else:
                node = hou.node(value)
                if node:
                    nodes.append(node)            
        return nodes

    def get_hou_nodes(self):
        from hou_node import get_hou_node
        return [get_hou_node(node) for node in self.get_nodes()]
    