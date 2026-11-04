#include "checksum.h"

uint32_t pn_e2e_adler32(const uint8_t *data, size_t length) {
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < length; i++) {
        a = (a + data[i]) % 65521;
        b = (b + a) % 65521;
    }
    return (b << 16) | a;
}
