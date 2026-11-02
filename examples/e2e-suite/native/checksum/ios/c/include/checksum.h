#ifndef PN_E2E_CHECKSUM_H
#define PN_E2E_CHECKSUM_H

#include <stddef.h>
#include <stdint.h>

uint32_t pn_e2e_adler32(const uint8_t *data, size_t length);

#endif
