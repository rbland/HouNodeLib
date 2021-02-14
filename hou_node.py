# The MetaHouNode and HouNode class..

import os
import sys
import hou

from hou_parm import MetaHouParm

def get_hou_node(node, *args, **kwargs):
    """
    Gets a HouNode instance for the specified node.
    The node parameter can be any of: str, hou.Node, HouNode
    """
    node_cls = MetaHouNode.get_node_cls(node)
    if node_cls == None:
        return None
    return node_cls(node, *args, **kwargs)
    
class MetaHouNode(type):
    """
    A meta class to track all HouNode subclasses.
    """
    NODE_TYPE_TO_CLASS = dict()
    DEFAULT_CLASS = None
    
    def __new__(cls, name, bases, class_dict):
        """
        Called when a new Base class is created using this metaclass.
        """
        # create the new class
        new_cls = type.__new__(cls, name, bases, class_dict)
        if cls.DEFAULT_CLASS == None:
            # if this is the first class declared (which will be HouNode)
            # store it as the default class
            cls.DEFAULT_CLASS = new_cls
        # associate the defined list of node types with the new class definition
        for node_type in new_cls.SUPPORTED_TYPES:
            cls.NODE_TYPE_TO_CLASS[node_type] = new_cls
        return new_cls

    @classmethod
    def get_sesi_node(cls, node):
        """
        Retrieves a Houdini node object from various inputs.
        """
        if isinstance(node, hou.Node):
            # object is already a SESI node
            return node
        if isisntance(node, str):
            # object is string (assume node path)
            return hou.node(node)
        if isinstance(node, HouNode):
            # object is another HouNode instance
            return node.get_sesi_node()
        return None
        
    @classmethod
    def get_node_cls(cls, node):
        """
        Retrieves a node class to use for the specified node.
        """
        node = cls.get_sesi_node(node)
        if node == None:
            return None
        node_type = node.type().name()
        return cls.NODE_TYPE_TO_CLASS.get(node_type, cls.DEFAULT_CLASS)
        
class HouNode(object):
    """
    The HouNode class represent a network node in Houdini.
    It extends the behavior provided by the SESI hou.Node class
    and provides various convience methods that can be used in
    scripts, tools and subclasses.
    """
    __metaclass__ = MetaHouNode
    
    # a list of all instances of HouNode or a sub-class
    _HOU_NODE_INSTANCES = []
    
    # a virtual list of node type names (e.g. ifd, geo, point, etc) that a sub-class should be instantiated to represent
    # In other words if a node is passed to the "get_node" function above whose type is in a class's "SUPPORTED_TYPES"  list,
    # the returned object will be an instance of the corresponding class.
    SUPPORTED_TYPES = []
    
    def __new__(cls, node, *args, **kwargs):
        """
        Constructor for a new HouNode object. If a HouNode
        instance was previously constructed for the node passed
        to the constructor. The same instance is returned.
        Otherwise a new instance is constructed and returned.
        """
        if args:
            node = cls.get_sesi_node(args.pop())
        elif 'node' in kwargs:
            node = cls.get_sesi_node(kwargs.pop('node'))
        else:
            node = hou.pwd()
        if not node:
            raise Exception('No Houdini node could be identified'
                            ' in the HouNode constructor.')
        new_instance = kwargs.pop('new_instance', False)
        if not new_instance:
            # if an instance has already been created for
            # the current node return that cached instance
            for instance in cls._HOU_NODE_INSTANCES:
                if instance._sesi_node == node:
                    return instance
        new_inst = object.__new__(cls)
        # supported in Houdini 11.0 and later
        #node.addEventCallback(hou.nodeEventType.BeingDeleted,
        #                      new_inst.on_node_deleted)
        cls._HOU_NODE_INSTANCES.append(new_inst)
        return new_inst
    
    def __init__(self, node, *args, **kwargs):
        """
        HouNode initializer.
        """
        self._sesi_node = MetaHouNode.get_sesi_node(node)
        
        self.magic_set_parms = kwargs.pop('magic_set_parms', True)
        self.magic_get_parms = kwargs.pop('magic_get_parms', True)
        self._py_attrs_persist = kwargs.pop('py_attrs_persist', False)
        self._node_parms = dict()
        self._node_method_names = []
        
        if self._py_attrs_persist:
            # restore previously saved python attribute values
            self.restore_python_attriubtes()
        # update parameter dictionary from node
        parm_names = kwargs.pop('parm_names', None)
        self.update_node_parms(parm_names)
        # update the list of method names from SESI node class
        method_names = kwargs.pop('method_names', None)
        self.update_node_methods(method_names)
        
    @classmethod
    def on_scene_saved(cls):
        """
        Callback just before the scene is saved. This method saves persistant
        python attributes onto the node objects which are flagged to do so.
        """ 
        cls._remove_deleted_nodes()
        for instance in cls._HOU_NODE_INSTANCES:
            if instance._py_attrs_persist:
                # save pickled python attributes to the Node's user data
                instance.save_python_attrs()

    @classmethod
    def on_scene_load(cls, sesi_nodes=None):
        """
        Callback just after a scene is loaded or the session is cleared.
        This method clears the list of HouNode instance references.
        """ 
        cls.clear_node_instances()
                
    @classmethod
    def _remove_deleted_nodes(cls):
        """
        Remove node entries from the instance list which have been deleted.
        """ 
        cls._HOU_NODE_INSTANCES[:] = (node for node in cls._HOU_NODE_INSTANCES 
                                      if node.node_was_deleted())

    @classmethod
    def clear_node_instances(cls):
        """
        Clears the list of HouNode instance references.
        """ 
        if cls._HOU_NODE_INSTANCES:
            cls._HOU_NODE_INSTANCES = []
                                      
    def update_node_parms(self, names=None):
        """
        Updates the dictionary mapping parameter names to NodeParm objects.
        """
        if names == None:
            # get the list of all parameter names from the SESI node.
            tuple_names = [tuple.name() for tuple in self._sesi_node.parmTuples()]
            parm_names = [parm.name() for parm in self._sesi_node.parms()]
            names = list(set(parm_names + tuple_names))
        self._node_parms = dict.fromkeys(names)
        
    def update_node_methods(self, method_names=None):
        """
        Updates the list of SESI node method names
        that can be called vicariously on this HouNode instance.
        """
        if method_names == None:
            method_names = dir(self._sesi_node)
        self._node_method_names = method_names
        
    def on_node_created(self):
        """
        Callback when a new node is created. This method should be
        overwritten to customize creation behavior and initialization.
        """
        pass
        
    def on_node_deleted(self):
        """
        Callback when this node is deleted. This method removes
        this instance from the HouNode instance list.
        """
        if hou.hipFile.isShuttingDown():
            # If the session or scene is being closed
            # clear the entire instance list
            self.clear_node_instances()
        else:
            while self in self._HOU_NODE_INSTANCES:
                self._HOU_NODE_INSTANCES.remove(self)

    def node_was_deleted(self):
        """
        Indicates if the Houdini node represented by
        this instance has been deleted.
        """
        if self._sesi_node == None:
            return True
        try:
            # call a method on the SESI node
            self._sesi_node.name()
        except hou.ObjectWasDeleted:
            # catch object deleted exception
            return True
        return False
                
    def __getattr__(self, key):
        """
        Overrides the attribute retrieval method for HouNode instances.
        This method is only called if a python attribute or method of the
        requested name was not found.
        """

        # check for a node parameter for the requested attribute name
        #
        
        # use the __dict__ object to retrieve attribute values
        magic_get_parms = self.__dict__.get('magic_get_parms', False)
        if magic_get_parms: 
            node_parms = self.__dict__.get('_node_parms', None)
            if node_parms and key in node_parms:
                return self.get_node_parm(key)
            
        # check for a method on the SESI node for the requested attribute name
        #
        method_names = self.__dict__.get('_node_method_names', None)
        sesi_node = self.__dict__.get('_sesi_node', None)
        if sesi_node and method_names and key in method_names:
            return getattr(sesi_node, key)
        
        # no valid attribute could be found
        raise AttributeError('Unknown attribute name "%s"' % key)
        
    def __setattr__(self, key, value):
        """
        """
        # check for a parameter with the name of the attribute being set
        #
        magic_set_parms = self.__dict__.get('magic_set_parms', False)
        if magic_set_parms:
            node_parms = self.__dict__.get('_node_parms', None)
            if node_parms and key in node_parms:
                node_parm = self.get_node_parm(key)
                node_parm.set_value(value)
                return
            
        # by default set the python instance attribute
        self.__dict__[key] = value
        
    def get_node_parm(self, parm_name):
        """
        Gets the NodeParm instance representing the specified
        parameter name for this node.
        """
        if parm_name not in self._node_parms:
            return None
        node_parm = self._node_parms[parm_name]
        if node_parm == None:
            node_parm = MetaHouParm.get_node_parm(self, parm_name)
            self._node_parms[parm_name] = node_parm
        return node_parm

    def _get_python_attributes(self):
        """
        Gets the mapping of pickleable python attribute name and values.
        """
        python_attrs = dict()
        for key, value in vars(self).iteritems():
            if key.startswith('_'):
                continue
            if isinstance(value, hou.Node):
                continue
            python_attrs[key] = value
        return python_attrs

    def save_python_attrs(self):
        """
        Pickles this instance's attributes and
        saves them to the Houdini node's user data.
        """
        python_attrs = self._get_python_attributes()
        value = string_utils.obj_to_str(python_attrs)
        self._sesi_node.setUserData('hou_node_py_attrs', value)

    def restore_python_attrs(self):
        """
        Restores previously pickled instance attributes
        from the Houdini node's user data.
        """
        value = self._sesi_node.userData('hou_node_py_attrs')
        python_attrs = string_utils.str_to_obj(python_attrs)
        restore_magic_set_parm = self.magic_set_parms
        self.magic_set_parms = False
        for key, value in python_attrs.iteritems():
            setattr(self, key, value)
        self.magic_set_parms = restore_magic_set_parm

    def __repr__(self):
        return '<%s path "%s" at %d>' % (self.__class__.__name__,
                                        self.path(), id(self))
