# Overview
A class that allows `hou.Node` from the Houdini Python API to be extended.

# Problem
When I started developing tools for Houdini in Python I discovered the `hou.Node` class provided by Side Effects Software was robust but limiting. I wanted to extend the `hou.Node` class with additional features to integrate with a pipeline. This was not possible; the `hou.Node` class cannot be directly instantiated because it is defined using a SWIG C++ plug-in.

# Solution
My solution was to create a new class `HouNode` that provides access to all `hou.Node` attributes vicariously through an override of the `__getattr__` method. The new class also provides access to node parameters as instance attributes allowing for more concise, pythonic code in its usage. The new custom `HouNode` and `HouParm` classes can now be freely sub-classed. In addition, the new classes can incorporate pipeline integration methods as needed.