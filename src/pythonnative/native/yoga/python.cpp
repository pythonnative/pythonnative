// Python host binding for the same Yoga core used by mobile runtimes.
#include <Python.h>
#include <yoga/Yoga.h>
extern "C" {
typedef void (*PNMeasure)(YGNodeConstRef, float, int, float, int, float*, float*);
static PNMeasure callback = nullptr;
static YGSize measure(YGNodeConstRef node, float w, YGMeasureMode wm, float h, YGMeasureMode hm) {
    float width = 0, height = 0;
    callback(node, w, static_cast<int>(wm), h, static_cast<int>(hm), &width, &height);
    return {width, height};
}
void pn_yoga_callback(PNMeasure fn) { callback = fn; }
void pn_yoga_measure(YGNodeRef node, int enabled) { YGNodeSetMeasureFunc(node, enabled ? measure : nullptr); }
static PyModuleDef module = {PyModuleDef_HEAD_INIT, "_yoga", "Yoga 3.2.1 host library", -1, nullptr};
PyMODINIT_FUNC PyInit__yoga() { return PyModule_Create(&module); }
}
