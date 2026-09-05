#pragma once
#include <yoga/Yoga.h>
#ifdef __cplusplus
extern "C" {
#endif
// Returns false for an unsupported or invalid layout property.
bool PNYogaSetStyle(YGNodeRef node, const char* key, const char* value);
#ifdef __cplusplus
}
#endif
