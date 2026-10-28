// The host build of the renderer core as an importable extension module.
// Python binds the C ABI in `include/pn_core.h` with ctypes; the module
// itself only gives the shared library a place on the import path.
#include <Python.h>

static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_core", "PythonNative renderer core (host build)", -1, nullptr};

PyMODINIT_FUNC PyInit__core() {
    return PyModule_Create(&module);
}
